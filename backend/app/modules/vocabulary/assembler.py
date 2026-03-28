from __future__ import annotations

from app.modules.capture.contracts import CaptureItemDTO
from app.modules.vocabulary.contracts import VocabularyFromCaptureResultDTO, VocabularyItemDTO
from app.modules.vocabulary.models import VocabularyItemModel


def to_vocabulary_item_dto(item: VocabularyItemModel) -> VocabularyItemDTO:
    return VocabularyItemDTO(
        id=item.id,
        user_id=item.user_id,
        english_lemma=item.english_lemma,
        russian_translation=item.russian_translation,
        context_definition_ru=item.context_definition_ru,
        source_sentence=item.source_sentence,
        source_url=item.source_url,
    )


def to_vocabulary_from_capture_result_dto(
    *,
    capture: CaptureItemDTO,
    vocabulary: VocabularyItemDTO,
    translation_note: str,
    created_new_vocabulary_item: bool,
    queued_for_review: bool,
) -> VocabularyFromCaptureResultDTO:
    return VocabularyFromCaptureResultDTO(
        capture=capture,
        vocabulary=vocabulary,
        translation_note=translation_note,
        created_new_vocabulary_item=created_new_vocabulary_item,
        queued_for_review=queued_for_review,
    )
