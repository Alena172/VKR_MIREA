from __future__ import annotations

import json
import logging
import re
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import pymorphy3 as pymorphy2

_log = logging.getLogger(__name__)

from app.modules.ai.schemas import (
    TranslateGlossaryItem,
    TranslateWithContextRequest,
    TranslateWithContextResponse,
)

if TYPE_CHECKING:
    from app.modules.ai.libretranslate_client import LibreTranslateClient

_morph = pymorphy2.MorphAnalyzer()


class TranslationService:
    _DIRECT_MAP = {
        "apple": "яблоко",
        "pear": "груша",
        "truck": "грузовик",
        "through": "через",
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
        model: str,
        translation_strict_remote: bool,
        remote_enabled: Callable[[], bool],
        chat_complete_async: Callable[..., Awaitable[str | None]],
        provider_unavailable_error: type[Exception],
        libretranslate_client: LibreTranslateClient | None = None,
    ) -> None:
        self._model = model
        self._translation_strict_remote = translation_strict_remote
        self._remote_enabled = remote_enabled
        self._chat_complete_async = chat_complete_async
        self._provider_unavailable_error = provider_unavailable_error
        self._libretranslate = libretranslate_client

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
        from app.modules.ai.free_dictionary_client import _FORCE_AI_WORDS
        lowered = self._normalize_english_text(text)
        if lowered in self._PHRASE_MAP:
            return False
        tokens = self._tokenize(lowered)
        if len(tokens) != 1:
            return False
        norm = self._normalize_token(tokens[0])
        return norm in self._AMBIGUOUS_MAP or lowered in _FORCE_AI_WORDS or norm in _FORCE_AI_WORDS

    def _build_remote_provider_note(self, payload: TranslateWithContextRequest) -> str:
        uses_glossary = bool(payload.glossary)
        uses_context = bool((payload.source_context or "").strip())
        prefix = "ai_disambiguation" if (uses_glossary or uses_context or self._looks_ambiguous(payload.text)) else "ai_translation"
        return f"{prefix}:{self._model}"

    def fast_translate_single_word(
        self,
        text: str,
        glossary: list[TranslateGlossaryItem] | None = None,
    ) -> str | None:
        normalized = self._normalize_english_text(text)
        if not normalized or " " in normalized:
            return None
        return self.pick_contextual_translation(normalized, None, glossary)

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

    def _lemmatize_ru(self, word: str) -> str:
        parsed = _morph.parse(word.strip())
        if not parsed:
            return word
        return parsed[0].normal_form

    def _all_normal_forms(self, word: str) -> set[str]:
        parsed = _morph.parse(word.strip())
        return {p.normal_form for p in parsed} if parsed else {word.lower()}

    def _is_single_word(self, text: str) -> bool:
        return len(text.strip().split()) == 1

    async def _libretranslate_word(
        self,
        word: str,
        source_context: str | None = None,
    ) -> str | None:
        if self._libretranslate is None:
            return None
        if source_context and source_context.strip():
            raw = await self._libretranslate.translate_word_in_context(
                word=word,
                sentence=source_context,
                all_normal_forms_fn=self._all_normal_forms,
            )
            if raw:
                return self._lemmatize_ru(raw)
            return None
        raw = await self._libretranslate.translate_word(word)
        if raw:
            return self._lemmatize_ru(raw)
        return None

    async def translate_with_context_async(
        self,
        payload: TranslateWithContextRequest,
    ) -> TranslateWithContextResponse:
        # Check user glossary first — if there's a match, skip LibreTranslate and AI entirely.
        if payload.glossary:
            glossary_hit = self._resolve_glossary_translation(payload.text, payload.source_context, payload.glossary)
            if glossary_hit:
                note = "glossary:user_match"
                _log.info("translate | provider=%-30s | word=%-20s | result=%s", note, payload.text, glossary_hit)
                return TranslateWithContextResponse(translated_text=glossary_hit, provider_note=note)

        if self._translation_strict_remote and not self._remote_enabled():
            raise self._provider_unavailable_error(
                "Translation provider is unavailable. "
                "AI-провайдер недоступен. Проверь AI_BASE_URL и AI_MODEL в .env."
            )

        # LibreTranslate level: try before AI for words and phrases.
        # Skip for known ambiguous words — LibreTranslate ignores word sense
        # disambiguation and always returns the most common meaning.
        if self._libretranslate is not None:
            skip_lt = payload.force_ai or self._looks_ambiguous(payload.text)
            if not skip_lt:
                if self._is_single_word(payload.text):
                    lt_result = await self._libretranslate_word(payload.text, payload.source_context)
                    if lt_result:
                        note = "libretranslate:word_in_context" if payload.source_context else "libretranslate:word"
                        _log.info("translate | provider=%-30s | word=%-20s | result=%s", note, payload.text, lt_result)
                        return TranslateWithContextResponse(
                            translated_text=lt_result,
                            provider_note=note,
                        )
                else:
                    lt_result = await self._libretranslate.translate_word(payload.text)
                    if lt_result:
                        _log.info("translate | provider=%-30s | word=%-20s | result=%s", "libretranslate:phrase", payload.text, lt_result[:40])
                        return TranslateWithContextResponse(
                            translated_text=lt_result,
                            provider_note="libretranslate:phrase",
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
        is_single = self._is_single_word(payload.text)
        if payload.force_ai and payload.source_context:
            disambiguation_note = (
                "ВАЖНО: это многозначное слово. "
                "Предложение-контекст является ГЛАВНЫМ сигналом — определи значение ТОЛЬКО по нему. "
                "Игнорируй самое частое или словарное значение, если контекст указывает на другое. "
            )
        else:
            disambiguation_note = ""
        content = await self._chat_complete_async(
            system_prompt=(
                "Ты переводчик EN→RU. "
                "ФОРМАТ ОТВЕТА — СТРОГО ОДНО СЛОВО (начальная форма: инфинитив или именительный падеж), "
                "если запрос — одно слово. "
                "Если запрос — фраза, верни только перевод фразы без лишних слов. "
                "Запрещено: предложения, пояснения, скобки, транслитерация, исходный текст. "
                f"{disambiguation_note}"
                "Если слово есть в глоссарии и подходит по контексту — используй его перевод."
            ),
            user_prompt=(
                f"{'Слово' if is_single else 'Фраза'}: {payload.text}\n"
                f"Предложение-контекст: {payload.source_context or '—'}\n"
                f"CEFR: {payload.cefr_level or 'unknown'}\n"
                f"Глоссарий: {glossary_json}\n"
                f"Переведи {'слово' if is_single else 'фразу'} на русский язык."
                + (" Ответ — ОДНО слово:" if is_single else " Ответ — только перевод фразы:")
            ),
            temperature=0.0,
            max_tokens=220,
        )
        if content:
            note = self._build_remote_provider_note(payload)
            _log.info("translate | provider=%-30s | word=%-20s | result=%s", note, payload.text, content.strip()[:40])
            return TranslateWithContextResponse(
                translated_text=content.strip().strip('"').lower(),
                provider_note=note,
            )
        if self._translation_strict_remote:
            raise self._provider_unavailable_error(
                "Translation provider request failed. Check AI_BASE_URL, AI_MODEL, AI_API_KEY and provider availability."
            )
        fallback = self.fallback_translate_with_context(payload)
        _log.info("translate | provider=%-30s | word=%-20s | result=%s", fallback.provider_note, payload.text, fallback.translated_text[:40])
        return fallback
