from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Awaitable, Callable

from app.modules.ai_services.contracts import (
    TranslateGlossaryItem,
    TranslateWithContextRequest,
    TranslateWithContextResponse,
)


class TranslationService:
    _DIRECT_MAP = {
        "apple": "яблоко",
        "pear": "груша",
        "truck": "грузовик",
        "through": "через",
        "book": "книга",
        "language": "язык",
        "word": "слово",
        "sentence": "предложение",
        "learn": "изучать",
        "study": "учиться",
        "speak": "говорить",
        "read": "читать",
        "write": "писать",
        "practice": "практиковать",
        "translate": "переводить",
        "hello": "привет",
        "world": "мир",
        "good": "хороший",
        "bad": "плохой",
        "small": "маленький",
        "big": "большой",
        "fast": "быстрый",
        "slow": "медленный",
        "home": "дом",
        "school": "школа",
        "work": "работа",
        "friend": "друг",
        "time": "время",
        "day": "день",
        "night": "ночь",
        "today": "сегодня",
        "tomorrow": "завтра",
        "yesterday": "вчера",
    }
    _AMBIGUOUS_MAP = {
        "right": {"left": "право", "correct": "правильный", "answer": "правильный"},
        "light": {"lamp": "свет", "dark": "свет", "weight": "легкий"},
        "book": {"read": "книга", "page": "книга", "ticket": "забронировать", "hotel": "забронировать"},
        "watch": {"movie": "смотреть", "video": "смотреть", "time": "часы"},
    }
    _PHRASE_MAP = {
        "look up": "искать",
        "find out": "выяснить",
        "turn on": "включить",
        "turn off": "выключить",
        "go on": "продолжать",
        "pick up": "подбирать",
    }

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        translation_strict_remote: bool,
        remote_enabled: Callable[[], bool],
        chat_complete_async: Callable[..., Awaitable[str | None]],
        provider_unavailable_error: type[Exception],
    ) -> None:
        self._provider = provider
        self._model = model
        self._translation_strict_remote = translation_strict_remote
        self._remote_enabled = remote_enabled
        self._chat_complete_async = chat_complete_async
        self._provider_unavailable_error = provider_unavailable_error

    def _tokenize(self, text: str) -> list[str]:
        return [part for part in re.split(r"[^a-zA-Z']+", text.lower()) if part]

    def _normalize_english_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def _normalize_token(self, token: str) -> str:
        irregular = {
            "children": "child",
            "men": "man",
            "women": "woman",
            "mice": "mouse",
            "went": "go",
            "gone": "go",
            "seen": "see",
            "saw": "see",
            "done": "do",
            "did": "do",
            "was": "be",
            "were": "be",
            "is": "be",
            "are": "be",
            "am": "be",
            "has": "have",
            "had": "have",
        }
        if token in irregular:
            return irregular[token]
        if token.endswith("ies") and len(token) > 3:
            return token[:-3] + "y"
        if token.endswith("ing") and len(token) > 5:
            stem = token[:-3]
            if len(stem) >= 2 and stem[-1] == stem[-2]:
                stem = stem[:-1]
            return stem
        if token.endswith("ed") and len(token) > 4:
            stem = token[:-2]
            if stem.endswith("i"):
                stem = stem[:-1] + "y"
            return stem
        if token.endswith("es") and len(token) > 4:
            return token[:-2]
        if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
            return token[:-1]
        return token

    def _resolve_glossary_translation(
        self,
        text: str,
        context: str | None,
        glossary: list[TranslateGlossaryItem],
    ) -> str | None:
        if not glossary:
            return None

        text_normalized = self._normalize_english_text(text)
        context_tokens = set(self._tokenize(context or ""))
        text_tokens = self._tokenize(text_normalized)
        normalized_text_tokens = {self._normalize_token(token) for token in text_tokens}

        exact_matches: list[TranslateGlossaryItem] = []
        token_matches: list[tuple[int, TranslateGlossaryItem]] = []

        for item in glossary:
            term = self._normalize_english_text(item.english_term)
            if not term:
                continue
            if term == text_normalized:
                exact_matches.append(item)
                continue

            term_tokens = self._tokenize(term)
            term_norm_tokens = {self._normalize_token(token) for token in term_tokens}
            if len(term_norm_tokens) == 1 and term_norm_tokens.intersection(normalized_text_tokens):
                score = 0
                source_tokens = set(self._tokenize(item.source_sentence or ""))
                if context_tokens and source_tokens:
                    score = len(context_tokens.intersection(source_tokens))
                token_matches.append((score, item))

        if exact_matches:
            if len(exact_matches) == 1:
                return exact_matches[0].russian_translation
            scored = sorted(
                exact_matches,
                key=lambda row: len(context_tokens.intersection(set(self._tokenize(row.source_sentence or "")))),
                reverse=True,
            )
            return scored[0].russian_translation

        if token_matches:
            token_matches.sort(key=lambda pair: pair[0], reverse=True)
            return token_matches[0][1].russian_translation

        return None

    def pick_contextual_translation(
        self,
        text: str,
        context: str | None,
        glossary: list[TranslateGlossaryItem] | None = None,
    ) -> str | None:
        glossary_translation = self._resolve_glossary_translation(text, context, glossary or [])
        if glossary_translation:
            return glossary_translation

        lowered = text.strip().lower()
        for phrase, translated in self._PHRASE_MAP.items():
            if lowered == phrase:
                return translated

        tokens = self._tokenize(lowered)
        if not tokens:
            return None
        norm_tokens = [self._normalize_token(token) for token in tokens]
        key = norm_tokens[0] if len(norm_tokens) == 1 else " ".join(norm_tokens)
        if key in self._DIRECT_MAP:
            return self._DIRECT_MAP[key]

        if len(norm_tokens) == 1 and norm_tokens[0] in self._AMBIGUOUS_MAP:
            context_tokens = set(self._tokenize(context or ""))
            variants = self._AMBIGUOUS_MAP[norm_tokens[0]]
            for trigger, translated in variants.items():
                if trigger in context_tokens:
                    return translated
        return None

    def _looks_ambiguous(self, text: str) -> bool:
        lowered = self._normalize_english_text(text)
        if lowered in self._PHRASE_MAP:
            return False
        tokens = self._tokenize(lowered)
        if len(tokens) != 1:
            return False
        return self._normalize_token(tokens[0]) in self._AMBIGUOUS_MAP

    def _build_remote_provider_note(self, payload: TranslateWithContextRequest) -> str:
        uses_glossary = bool(payload.glossary)
        uses_context = bool((payload.source_context or "").strip())
        if uses_glossary or uses_context or self._looks_ambiguous(payload.text):
            return f"ai_disambiguation:{self._provider}/{self._model}"
        return f"ai_translation:{self._provider}/{self._model}"

    def fast_translate_single_word(
        self,
        text: str,
        glossary: list[TranslateGlossaryItem] | None = None,
    ) -> str | None:
        normalized = self._normalize_english_text(text)
        if not normalized or " " in normalized:
            return None
        return self.pick_contextual_translation(
            normalized,
            None,
            glossary,
        )

    def heuristic_translate(
        self,
        text: str,
        context: str | None,
        glossary: list[TranslateGlossaryItem] | None = None,
    ) -> str:
        picked = self.pick_contextual_translation(text, context, glossary)
        if picked:
            return picked

        tokens = self._tokenize(text)
        if not tokens:
            return text.strip() or "перевод не найден"
        normalized = [self._normalize_token(token) for token in tokens]
        counts = Counter(normalized)
        if len(counts) == 1:
            only = next(iter(counts))
            fallback = self.pick_contextual_translation(only, context, glossary)
            if fallback:
                return fallback
            return only
        mapped = [self.pick_contextual_translation(token, context, glossary) or token for token in normalized]
        return " ".join(mapped)

    def fallback_translate_with_context(
        self,
        payload: TranslateWithContextRequest,
    ) -> TranslateWithContextResponse:
        translated = self.heuristic_translate(
            payload.text,
            payload.source_context,
            payload.glossary,
        )
        level_note = f" CEFR={payload.cefr_level}." if payload.cefr_level else ""
        context_note = " Context applied." if payload.source_context else ""
        return TranslateWithContextResponse(
            translated_text=translated,
            provider_note=f"local_heuristic EN->RU.{context_note}{level_note}",
        )

    async def translate_with_context_async(
        self,
        payload: TranslateWithContextRequest,
    ) -> TranslateWithContextResponse:
        if self._translation_strict_remote and not self._remote_enabled():
            raise self._provider_unavailable_error(
                "Translation provider is unavailable. "
                "Use AI_PROVIDER=ollama or set AI_PROVIDER=openai_compatible with AI_API_KEY."
            )

        glossary_json = json.dumps(
            [
                {
                    "english_term": item.english_term,
                    "russian_translation": item.russian_translation,
                    "source_sentence": item.source_sentence,
                }
                for item in payload.glossary[:200]
            ],
            ensure_ascii=False,
        )
        content = await self._chat_complete_async(
            system_prompt=(
                "Ты переводчик EN->RU для русскоязычного студента английского. "
                "Всегда учитывай контекст и пользовательский глоссарий. "
                "Если термин есть в глоссарии и подходит по контексту, используй перевод из глоссария. "
                "Верни только итоговый перевод на русском без комментариев. "
                "Если входной текст это одно слово или короткая фраза, верни только перевод этого слова/фразы, "
                "а не полное предложение."
            ),
            user_prompt=(
                f"Текст: {payload.text}\n"
                f"Уровень CEFR: {payload.cefr_level or 'unknown'}\n"
                f"Контекст: {payload.source_context or 'none'}\n"
                f"Глоссарий пользователя (JSON): {glossary_json}\n"
                "Формат ответа: только перевод, без пояснений и без исходного текста."
            ),
            temperature=0.0,
            max_tokens=220,
        )
        if content:
            return TranslateWithContextResponse(
                translated_text=content.strip().strip('"'),
                provider_note=self._build_remote_provider_note(payload),
            )
        if self._translation_strict_remote:
            raise self._provider_unavailable_error(
                "Translation provider request failed. Check AI_BASE_URL, AI_MODEL, AI_API_KEY and provider availability."
            )
        return self.fallback_translate_with_context(payload)
