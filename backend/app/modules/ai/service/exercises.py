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

    def _parse_sentence_translation_payload(self, raw: str) -> tuple[str, str] | None:
        payload = _extract_json_payload(raw)
        if not isinstance(payload, dict):
            return None

        sentence_en = str(payload.get("sentence_en", "")).strip()
        sentence_ru = str(payload.get("sentence_ru", "")).strip()
        if not sentence_en or not sentence_ru:
            return None
        return self._sanitize_generated_sentence(sentence_en), sentence_ru.strip().strip('"')

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

    async def generate_sentence_pair(
        self,
        seed: ExerciseSeed,
        cefr_level: str,
    ) -> tuple[str, str] | None:
        history = self._recent_sentences.setdefault(seed.english_lemma.strip().lower(), deque(maxlen=8))
        prompts = [
            (
                "You are an English teacher for a Russian-speaking learner. "
                "Return only JSON with keys sentence_en and sentence_ru.",
                (
                    f"Target word: {seed.english_lemma}\n"
                    f"Target translation in Russian: {seed.russian_translation}\n"
                    f"CEFR level: {cefr_level}\n"
                    f"Avoid repeating these recent sentences: {json.dumps(list(history), ensure_ascii=False)}\n"
                    f"User context hint: {seed.source_sentence or 'none'}\n"
                    "Generate exactly one natural English sentence and its Russian translation.\n"
                    "Constraints:\n"
                    "- everyday context only\n"
                    "- include the target word exactly once in sentence_en\n"
                    "- preserve meaning exactly in sentence_ru\n"
                    "- sentence_ru must use the provided Russian translation or its correct inflected form\n"
                    "- no markdown\n"
                    'Format: {"sentence_en":"...","sentence_ru":"..."}'
                ),
            ),
            (
                "You are an English teacher for a Russian-speaking learner. "
                "Return only JSON with keys sentence_en and sentence_ru.",
                (
                    f"Target word: {seed.english_lemma}\n"
                    f"Mandatory Russian translation for the target word: {seed.russian_translation}\n"
                    f"CEFR level: {cefr_level}\n"
                    "The translation must not replace the target word with a different object or concept.\n"
                    "Generate exactly one sentence pair.\n"
                    'Format: {"sentence_en":"...","sentence_ru":"..."}'
                ),
            ),
        ]

        for system_prompt, user_prompt in prompts:
            content = await self._chat_complete_async(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.15,
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
        history = self._recent_sentences.setdefault(word, deque(maxlen=8))
        for _ in range(self._max_retries + 2):
            content = await self._chat_complete_async(
                system_prompt=(
                    "You are an English teacher. Generate one natural, high-frequency, grammatically correct "
                    "English sentence for a Russian-speaking learner. "
                    "Use plain modern spoken/written English and avoid bookish phrasing."
                ),
                user_prompt=(
                    f"Target word: {word}\n"
                    f"CEFR level: {cefr_level}\n"
                    f"Avoid repeating these recent sentences: {json.dumps(list(history), ensure_ascii=False)}\n"
                    "Constraints:\n"
                    "- one sentence only\n"
                    "- everyday context (home, study, work, shopping, transport)\n"
                    "- avoid fantasy, rare names, unusual locations\n"
                    "- include the target word exactly once\n"
                    "- prefer short natural collocations used by natives\n"
                    "- avoid stiff phrases like 'during the quiet hours' and similar literary wording\n"
                    "- do not use markdown, quotes, bullets, numbering\n"
                    "- output sentence only"
                ),
                temperature=0.2,
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
                if self._translation_contains_target(translated, seed.russian_translation):
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
