from __future__ import annotations

from app.modules.vocabulary.contracts import (
    VocabularyFromCaptureResultDTO,
    VocabularyItemDTO,
)
from app.modules.vocabulary.models import VocabularyItemModel


def to_vocabulary_item_dto(item: VocabularyItemModel) -> VocabularyItemDTO:
    return VocabularyItemDTO(
        id=item.id,
        user_id=item.user_id,
        english_lemma=item.english_lemma,
        russian_translation=item.russian_translation,
        context_definition_ru=item.context_definition_ru,
        context_definition_source=item.context_definition_source,
        context_definition_confidence=item.context_definition_confidence,
        definition_reused_from_item_id=item.definition_reused_from_item_id,
        source_sentence=item.source_sentence,
        source_url=item.source_url,
    )


def to_vocabulary_from_capture_result_dto(
    *,
    vocabulary: VocabularyItemDTO,
) -> VocabularyFromCaptureResultDTO:
    return VocabularyFromCaptureResultDTO(
        vocabulary=vocabulary,
    )
