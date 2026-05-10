"""Backward-compat shim — capture logic lives in VocabularyService."""
from __future__ import annotations

from app.modules.vocabulary.schemas import CaptureDTO, VocabularyItemDTO


async def capture_to_vocabulary(
    *,
    user_id: int,
    selected_text: str,
    source_url: str | None,
    source_sentence: str | None,
    force_new_vocabulary_item: bool,
    _service=None,
) -> CaptureDTO:
    """Thin shim used by Celery tasks and legacy tests."""
    if _service is None:
        raise RuntimeError(
            "capture_to_vocabulary requires a VocabularyService instance. "
            "Use VocabularyService.capture_to_vocabulary() directly."
        )
    item: VocabularyItemDTO = await _service.capture_to_vocabulary(
        user_id=user_id,
        selected_text=selected_text,
        source_url=source_url,
        source_sentence=source_sentence,
        force_new_vocabulary_item=force_new_vocabulary_item,
    )
    return CaptureDTO(vocabulary=item)
