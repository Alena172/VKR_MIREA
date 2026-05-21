from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections import deque
from collections.abc import Awaitable, Callable

from app.modules.ai.schemas import ExerciseSeed, TranslateGlossaryItem
from app.modules.ai.service.translation import TranslationService


def _extract_json_payload(raw: str) -> dict | list | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    fenced = re.search(r"```json\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            return None
    return None


class ExerciseMaterialService:
    def __init__(
        self,
        *,
        max_retries: int,
        remote_enabled: Callable[[], bool],
        chat_complete_async: Callable[..., Awaitable[str | None]],
        provider_unavailable_error: type[Exception],
        translation_service: TranslationService,
        recent_sentences: dict[str, deque[str]],
    ) -> None:
        self._max_retries = max_retries
        self._remote_enabled = remote_enabled
        self._chat_complete_async = self._wrap_async_chat_complete(chat_complete_async)
        self._provider_unavailable_error = provider_unavailable_error
        self._translation_service = translation_service
        self._recent_sentences = recent_sentences

    def _wrap_async_chat_complete(
        self,
        callback: Callable[..., Awaitable[str | None]] | Callable[..., str | None],
    ) -> Callable[..., Awaitable[str | None]]:
        if inspect.iscoroutinefunction(callback):
            return callback

        async def _wrapped(**kwargs) -> str | None:
            return await asyncio.to_thread(callback, **kwargs)

        return _wrapped

    def _sentence_word_limits(self, cefr_level: str) -> tuple[int, int]:
        if cefr_level in {"A1", "A2"}:
            return (6, 18)
        if cefr_level in {"B1", "B2"}:
            return (8, 24)
        return (10, 28)

    def _is_sentence_suitable(self, sentence: str, target_word: str, cefr_level: str) -> bool:
        text = re.sub(r"\s+", " ", sentence.strip())
        if not text:
            return False
        if text.count(".") + text.count("!") + text.count("?") > 2:
            return False
        if not re.search(rf"\b{re.escape(target_word)}\b", text, flags=re.IGNORECASE):
            return False

        min_words, max_words = self._sentence_word_limits(cefr_level)
        words = re.findall(r"[A-Za-z']+", text)
        if len(words) < min_words or len(words) > max_words:
            return False

        disallowed_tokens = {"africa", "mars", "wizard", "dragon", "kingdom", "galaxy"}
        lowered = {token.lower() for token in words}
        return not bool(lowered.intersection(disallowed_tokens))

    def _sanitize_generated_sentence(self, text: str) -> str:
        candidate = text.strip().strip('"').strip("'")
        candidate = candidate.replace("**", "").replace("__", "").replace("`", "")
        return re.sub(r"\s+", " ", candidate).strip()

    def _is_sentence_ru_valid(self, sentence_ru: str) -> bool:
        """Проверяет, что русский перевод — полное предложение, а не обрывок."""
        cleaned = sentence_ru.strip()
        if not cleaned:
            return False
        all_words = re.findall(r"[А-Яа-яЁёA-Za-z]+", cleaned)
        if len(all_words) < 3:
            return False
        ru_words = [w for w in all_words if re.search(r"[А-Яа-яЁё]", w)]
        return len(ru_words) / len(all_words) >= 0.7

    def _parse_sentence_translation_payload(self, raw: str) -> tuple[str, str] | None:
        payload = _extract_json_payload(raw)
        if not isinstance(payload, dict):
            return None

        sentence_en = str(payload.get("sentence_en", "")).strip()
        sentence_ru = str(payload.get("sentence_ru", "")).strip().strip('"')
        if not sentence_en or not sentence_ru:
            return None
        if not self._is_sentence_ru_valid(sentence_ru):
            return None
        return self._sanitize_generated_sentence(sentence_en), sentence_ru

    def _translation_contains_target(self, translated_text: str, target_translation: str) -> bool:
        target_norm = target_translation.strip().lower().replace("ё", "е")
        target_norm = re.sub(r"[^а-яa-z]", "", target_norm)
        if not target_norm:
            return True
        prefix_len = max(4, len(target_norm) - 3)
        target_prefix = target_norm[:prefix_len]
        translated_tokens = re.findall(r"[А-Яа-яЁёA-Za-z-]+", translated_text)
        for token in translated_tokens:
            token_norm = token.strip().lower().replace("ё", "е")
            token_norm = re.sub(r"[^а-яa-z]", "", token_norm)
            if token_norm[:prefix_len] == target_prefix:
                return True
        return False

    # Ситуации для случайного выбора — чтобы предложения не повторяли контекст добавления слова
    _SITUATION_POOL = [
        "at home in the evening",
        "at work during a meeting",
        "in a café with a friend",
        "while shopping at a store",
        "on public transport",
        "during a phone call",
        "at university or school",
        "while cooking dinner",
        "on a weekend trip",
        "while watching a film",
        "at a gym or sports class",
        "while reading the news",
        "at a doctor's appointment",
        "while planning a holiday",
        "at a family dinner",
    ]

    async def generate_sentence_pair(
        self,
        seed: ExerciseSeed,
        cefr_level: str,
    ) -> tuple[str, str] | None:
        import random
        history = self._recent_sentences.setdefault(seed.english_lemma.strip().lower(), deque(maxlen=8))

        # Берём случайную ситуацию — НЕ связанную с исходным контекстом слова
        situation = random.choice(self._SITUATION_POOL)

        system_prompt = (
            "You are an English teacher creating translation exercises for Russian-speaking learners.\n"
            "Your task: write ONE English sentence using the target word, then translate it into Russian.\n"
            "\n"
            "Requirements for sentence_en:\n"
            "- sounds like something a real person would say in everyday life\n"
            "- uses the target word in a NATURAL, COMMON collocation — the word must fit its typical usage\n"
            "- before finalising, ask yourself: 'Would a native English speaker say this?' If no — rewrite\n"
            "- must fit the given situation\n"
            "- do NOT copy or paraphrase the word's original context — invent a fresh sentence\n"
            "- no literary or bookish phrasing\n"
            "\n"
            "CRITICAL — reject and rewrite if sentence_en:\n"
            "- uses the word in an unusual or impossible collocation (e.g. 'booking a book', 'discover a skill')\n"
            "- sounds like a textbook drill sentence\n"
            "- uses the word in a meaning that doesn't match the Russian translation provided\n"
            "\n"
            "Requirements for sentence_ru:\n"
            "- complete, grammatically correct Russian sentence\n"
            "- correct case, gender, number and tense agreement throughout\n"
            "- no English words, no transliteration\n"
            "- natural Russian — how a native speaker would actually say it\n"
            "\n"
            "Return ONLY JSON: {\"sentence_en\":\"...\",\"sentence_ru\":\"...\"}. No markdown, no comments."
        )

        prompts = [
            (
                f"Target word: {seed.english_lemma}\n"
                f"Russian meaning: {seed.russian_translation}\n"
                f"CEFR level: {cefr_level}\n"
                f"Situation: {situation}\n"
                f"Already used sentences (do not repeat): {json.dumps(list(history), ensure_ascii=False)}\n"
                "\n"
                f"Think about how '{seed.english_lemma}' is typically used by native speakers in everyday English.\n"
                "Write a sentence where this word appears in a natural, common collocation for the given situation.\n"
                "Check: would a native speaker say this? If not, choose a different situation.\n"
                'Return: {"sentence_en":"...","sentence_ru":"..."}'
            ),
            (
                f"Target word: {seed.english_lemma} (Russian: {seed.russian_translation})\n"
                f"CEFR: {cefr_level}, setting: {situation}\n"
                "\n"
                f"Write a short natural English sentence using '{seed.english_lemma}' in its most common everyday meaning.\n"
                "The collocation must be normal and natural — something natives actually say.\n"
                "Translate to Russian with correct grammar.\n"
                'Return: {"sentence_en":"...","sentence_ru":"..."}'
            ),
            (
                f"Word: {seed.english_lemma} = {seed.russian_translation}\n"
                f"Level: {cefr_level}\n"
                "\n"
                f"Use '{seed.english_lemma}' in a simple, natural English sentence. Pick the most typical way this word is used.\n"
                "Translate to Russian. Grammar must be correct.\n"
                'Return: {"sentence_en":"...","sentence_ru":"..."}'
            ),
        ]

        for user_prompt in prompts:
            content = await self._chat_complete_async(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=180,
            )
            if not content:
                continue
            pair = self._parse_sentence_translation_payload(content)
            if not pair:
                continue
            sentence_en, sentence_ru = pair
            word = seed.english_lemma.strip().lower()
            if (
                self._is_sentence_suitable(sentence_en, word, cefr_level)
                and self._translation_contains_target(sentence_ru, seed.russian_translation)
                and sentence_en not in history
            ):
                history.append(sentence_en)
                return sentence_en, sentence_ru
        return None

    async def generate_sentence_with_word(
        self,
        *,
        word: str,
        cefr_level: str,
    ) -> str | None:
        import random
        history = self._recent_sentences.setdefault(word, deque(maxlen=8))
        for _ in range(self._max_retries + 2):
            situation = random.choice(self._SITUATION_POOL)
            content = await self._chat_complete_async(
                system_prompt=(
                    "You are an English teacher. Write one natural English sentence for a Russian-speaking learner.\n"
                    "The sentence must sound like something a real person would actually say — not a textbook drill.\n"
                    "Use the target word in its most typical, natural collocation.\n"
                    "Before writing, ask yourself: 'Would a native speaker say this?' If not — choose differently.\n"
                    "Use plain modern English. No literary phrasing. Output the sentence only, no markdown."
                ),
                user_prompt=(
                    f"Target word: {word}\n"
                    f"CEFR level: {cefr_level}\n"
                    f"Situation: {situation}\n"
                    f"Avoid repeating: {json.dumps(list(history), ensure_ascii=False)}\n"
                    "Rules:\n"
                    "- one sentence only\n"
                    "- use the target word exactly once in a natural, common collocation\n"
                    "- must fit the given situation\n"
                    "- output the sentence only, no quotes or bullets"
                ),
                temperature=0.75,
                max_tokens=80,
            )
            if not content:
                continue
            candidate = self._sanitize_generated_sentence(content)
            if self._is_sentence_suitable(candidate, word, cefr_level) and candidate not in history:
                history.append(candidate)
                return candidate
        return None

    async def build_sentence_for_word(self, seed: ExerciseSeed, cefr_level: str | None = None) -> str:
        if not self._remote_enabled():
            raise self._provider_unavailable_error(
                "Sentence generation requires remote AI provider. "
                "AI-провайдер недоступен. Проверь AI_BASE_URL и AI_MODEL в .env."
            )

        word = seed.english_lemma.strip().lower()
        level = (cefr_level or "A2").upper()
        remote_sentence = await self.generate_sentence_with_word(word=word, cefr_level=level)
        if remote_sentence:
            return remote_sentence

        raise self._provider_unavailable_error(
            "Sentence generation request failed. Check AI_BASE_URL, AI_MODEL and provider availability."
        )

    async def translate_sentence_for_seed(self, sentence_en: str, seed: ExerciseSeed) -> str:
        if self._remote_enabled():
            prompts = [
                (
                    "Переведи английское предложение на русский. Верни только перевод без комментариев.",
                    (
                        f"Предложение: {sentence_en}\n"
                        f"Ключевое слово: {seed.english_lemma}\n"
                        f"Желаемый перевод ключевого слова: {seed.russian_translation}\n"
                        "Обязательно сохрани смысл предложения."
                    ),
                ),
                (
                    "Переведи английское предложение на русский. Верни только перевод без комментариев.",
                    (
                        f"Предложение: {sentence_en}\n"
                        f"Ключевое слово: {seed.english_lemma}\n"
                        f"Обязательный перевод ключевого слова: {seed.russian_translation}\n"
                        "Используй именно этот перевод или его корректную падежную форму. "
                        "Не заменяй ключевое слово другим предметом, фруктом или понятием."
                    ),
                ),
            ]
            for system_prompt, user_prompt in prompts:
                content = await self._chat_complete_async(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.0,
                    max_tokens=140,
                )
                if not content:
                    continue
                translated = content.strip().strip('"')
                if (
                    self._is_sentence_ru_valid(translated)
                    and self._translation_contains_target(translated, seed.russian_translation)
                ):
                    return translated

        translated = self._translation_service.heuristic_translate(
            sentence_en,
            sentence_en,
            [
                TranslateGlossaryItem(
                    english_term=seed.english_lemma,
                    russian_translation=seed.russian_translation,
                    source_sentence=seed.source_sentence,
                )
            ],
        )
        return translated or seed.russian_translation
