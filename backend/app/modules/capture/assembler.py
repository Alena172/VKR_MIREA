from __future__ import annotations

from app.modules.capture.contracts import CaptureItemDTO
from app.modules.capture.models import CaptureItemModel


def to_capture_item_dto(item: CaptureItemModel) -> CaptureItemDTO:
    return CaptureItemDTO(
        id=item.id,
        user_id=item.user_id,
        selected_text=item.selected_text,
        source_url=item.source_url,
        source_sentence=item.source_sentence,
    )
