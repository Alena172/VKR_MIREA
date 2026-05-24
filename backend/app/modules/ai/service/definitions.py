"""Сервис генерации и очистки контекстных определений для словаря."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable


class DefinitionService:
    """Генерация и санитизация английских определений слов."""

    def __init__(
        self,
        *,
        chat_complete_async: Callable[..., Awaitable[str | None]],
    ) -> None:
        self._chat_complete_async = chat_complete_async

    def _extract_definition_from_source_sentence(
        self,
        *,
        english_lemma: str,
        source_sentence: str | None,
    ) -> str | None:
        """Пытается извлечь определение прямо из предложения вида `X is ...`."""
        raw = (source_sentence or "").strip()
        if not raw:
            return None

        lemma = re.escape(english_lemma.strip())
        patterns = (
            rf"^(?:an?|the)\s+{lemma}\s+(?:is|are)\s+",
            rf"^{lemma}\s+(?:is|are)\s+",
        )
        candidate = raw
        for pattern in patterns:
            updated = re.sub(pattern, "", candidate, flags=re.IGNORECASE)
            if updated != candidate:
                candidate = updated
                break

        candidate = candidate.strip(" -,:;")
        if not candidate or candidate == raw:
            return None
        if candidate and candidate[-1] not in ".!?":
            candidate = f"{candidate}."
        return candidate[0].upper() + candidate[1:]

    def _fallback_context_definition(
        self,
        *,
        english_lemma: str,
        source_sentence: str | None,
    ) -> str | None:
        """Fallback: если AI не помог, пробует вытащить определение из исходного предложения."""
        return self._extract_definition_from_source_sentence(
            english_lemma=english_lemma,
            source_sentence=source_sentence,
        )

    def sanitize_context_definition(
        self,
        *,
        english_lemma: str,
        russian_translation: str,
        source_sentence: str | None,
        definition: str | None,
    ) -> str | None:
        """Чистит AI-ответ от мета-фраз и приводит определение к словарному виду."""
        cleaned = (definition or "").strip().strip('"')
        if not cleaned:
            return self._fallback_context_definition(
                english_lemma=english_lemma,
                source_sentence=source_sentence,
            )

        cleaned = (
            cleaned.replace("‘", "'")
            .replace("’", "'")
            .replace("“", '"')
            .replace("”", '"')
        )
        # Удаляем мета-фразы вида "In this context, 'X' describes/means/refers to..."
        cleaned = re.sub(r"^Here'?s?\s+(?:is\s+)?the\s+definition:?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^Definition:?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            rf"^In this context,\s*['\"]?{re.escape(english_lemma)}['\"]?\s+\w+\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"^In this context,\s*['\"]?{re.escape(english_lemma)}['\"]?\s+means\s+['\"].+?['\"]\s+in Russian\.\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"^['\"]?{re.escape(english_lemma)}['\"]?\s+means\s+['\"].+?['\"]\s+in Russian(?:\s+in the intended learning context)?\.?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"Something described as ['\"].+?['\"] in Russian,?\s*used in the intended learning context\.?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^It signifies\s+", "", cleaned, flags=re.IGNORECASE)
        # Удаляем хвост вида ". It signifies ... «русское слово»."
        cleaned = re.sub(r"\.\s+It signifies\s+.+$", ".", cleaned, flags=re.IGNORECASE | re.DOTALL)
        # Удаляем упоминание русского перевода в конце: , corresponding to ... "слово".
        cleaned = re.sub(r",?\s+corresponding to\s+.+?[\"'«»][^\"'«»]+[\"'«»]\.?\s*$", ".", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace("Example context:", "").strip(" -,:;")

        extracted = self._extract_definition_from_source_sentence(
            english_lemma=english_lemma,
            source_sentence=cleaned,
        )
        if extracted:
            return extracted

        if cleaned:
            if cleaned[-1] not in ".!?":
                cleaned = f"{cleaned}."
            return cleaned[0].upper() + cleaned[1:]

        return self._fallback_context_definition(
            english_lemma=english_lemma,
            source_sentence=source_sentence,
        )

    def generate_context_definition_fast(
        self,
        *,
        english_lemma: str,
        russian_translation: str,
        source_sentence: str | None,
    ) -> str | None:
        """Быстрый путь: использует исходное предложение как источник определения без AI."""
        return self.sanitize_context_definition(
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            source_sentence=source_sentence,
            definition=source_sentence,
        )

    async def generate_context_definition_async(
        self,
        *,
        english_lemma: str,
        russian_translation: str,
        source_sentence: str | None,
        cefr_level: str | None = None,
    ) -> str | None:
        """Генерирует английское определение конкретного смысла слова."""

        if source_sentence:
            sense_hint = (
                f"The word appears in this sentence: \"{source_sentence}\"\n"
                f"Its meaning in this sentence translates to Russian as \"{russian_translation}\".\n"
                "Define ONLY this specific sense as used in the sentence above."
            )
        else:
            sense_hint = (
                f"Russian translation of the intended sense: \"{russian_translation}\".\n"
                "Define ONLY the sense that matches this Russian translation."
            )

        content = await self._chat_complete_async(
            system_prompt=(
                "You are an English lexicography assistant writing dictionary definitions.\n"
                "Write a precise 1-2 sentence English definition for ONE specific sense of a word.\n"
                "Use the context sentence and Russian translation to identify the correct sense.\n"
                "\n"
                "OUTPUT FORMAT: the definition text only — no label, no preamble, no commentary.\n"
                "Begin directly with the meaning. Examples of correct output:\n"
                "  Having little weight; easy to lift or carry.\n"
                "  To reserve a place, ticket, or accommodation in advance.\n"
                "  A period of operating or managing something continuously.\n"
                "\n"
                "CRITICAL — never mention the word being defined anywhere in the definition,\n"
                "neither in English nor in Russian (not even as part of a phrase or example).\n"
                "Use 'it', 'someone', 'something', or a neutral paraphrase instead.\n"
                "\n"
                "FORBIDDEN openers (never start with these):\n"
                "  'In this context', 'Here is the definition', 'This word', 'It signifies',\n"
                "  'The word', 'Definition:', 'X means', 'X refers to', any Russian text."
            ),
            user_prompt=(
                f"Word: {english_lemma}\n"
                f"{sense_hint}\n"
                f"CEFR level of the learner: {cefr_level or 'unknown'}\n"
                "Definition:"
            ),
            temperature=0.1,
            max_tokens=220,
        )
        if content:
            cleaned = self.sanitize_context_definition(
                english_lemma=english_lemma,
                russian_translation=russian_translation,
                source_sentence=source_sentence,
                definition=content,
            )
            if cleaned and len(cleaned) >= 20:
                return cleaned
        return self._fallback_context_definition(
            english_lemma=english_lemma,
            source_sentence=source_sentence,
        )
