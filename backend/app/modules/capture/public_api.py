from __future__ import annotations

from app.modules.capture.assembler import to_capture_item_dto
from app.modules.capture.contracts import CaptureItemDTO
from app.modules.capture.repository import capture_repository

__all__ = [
    "CaptureItemDTO",
    "capture_public_api",
]


class CapturePublicApi:
    @staticmethod
    def create(db, payload, *, auto_commit: bool = True) -> CaptureItemDTO:
        item = capture_repository.create(
            db,
            payload,
            auto_commit=auto_commit,
        )
        return to_capture_item_dto(item)

    @staticmethod
    def list_items(db, user_id: int | None) -> list[CaptureItemDTO]:
        return [to_capture_item_dto(item) for item in capture_repository.list_items(db, user_id=user_id)]


capture_public_api = CapturePublicApi()
