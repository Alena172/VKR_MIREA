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

        content = await self._chat_complete_async(
            system_prompt=(
                "You are an English lexicography assistant. "
                "Write a complete and precise definition of the English word sense from the context. "
                "Write in English only, 1-2 sentences, concise and clear."
            ),
            user_prompt=(
                f"Word: {english_lemma}\n"
                f"Russian translation: {russian_translation}\n"
                f"Context: {source_sentence or 'not provided'}\n"
                f"CEFR: {cefr_level or 'unknown'}\n"
                "Return only the English definition for this sense."
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
