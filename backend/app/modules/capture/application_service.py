from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.application import application_access
from app.modules.capture.contracts import CaptureItemDTO
from app.modules.capture.repository import capture_repository
from app.modules.capture.schemas import CaptureCreate


class CaptureApplicationService:
    def list_items(
        self,
        *,
        db: Session,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> list[CaptureItemDTO]:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=requested_user_id,
            current_user_id=current_user_id,
        )
        from app.modules.capture.public_api import capture_public_api

        return capture_public_api.list_items(db, user_id=target_user_id)

    def create_item(
        self,
        *,
        db: Session,
        payload: CaptureCreate,
        current_user_id: int,
    ) -> CaptureItemDTO:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=payload.user_id,
            current_user_id=current_user_id,
        )
        application_access.ensure_user_exists(db=db, user_id=target_user_id)
        from app.modules.capture.public_api import capture_public_api

        return capture_public_api.create(
            db,
            payload.model_copy(update={"user_id": target_user_id}),
        )


capture_application_service = CaptureApplicationService()
