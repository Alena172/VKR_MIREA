from __future__ import annotations

from dataclasses import dataclass

from app.modules.capture.contracts import CaptureItemDTO


@dataclass(frozen=True)
class VocabularyItemDTO:
    id: int
    user_id: int
    english_lemma: str
    russian_translation: str
    context_definition_ru: str | None
    context_definition_source: str | None
    context_definition_confidence: str | None
    definition_reused_from_item_id: int | None
    source_sentence: str | None
    source_url: str | None


@dataclass(frozen=True)
class VocabularyFromCaptureResultDTO:
    capture: CaptureItemDTO
    vocabulary: VocabularyItemDTO
    translation_note: str
    created_new_vocabulary_item: bool
    queued_for_review: bool
