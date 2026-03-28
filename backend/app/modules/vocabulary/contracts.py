from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VocabularyItemDTO:
    id: int
    user_id: int
    english_lemma: str
    russian_translation: str
    context_definition_ru: str | None
    source_sentence: str | None
    source_url: str | None
