from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.capture.repository import capture_repository
from app.modules.capture.schemas import CaptureCreate, CaptureItem
from app.modules.users.repository import users_repository


class CaptureApplicationService:
    def list_items(
        self,
        *,
        db: Session,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> list[CaptureItem]:
        target_user_id = self._resolve_target_user_id(
            requested_user_id=requested_user_id,
            current_user_id=current_user_id,
        )
        return capture_repository.list_items(db, user_id=target_user_id)

    def create_item(
        self,
        *,
        db: Session,
        payload: CaptureCreate,
        current_user_id: int,
    ) -> CaptureItem:
        target_user_id = self._resolve_target_user_id(
            requested_user_id=payload.user_id,
            current_user_id=current_user_id,
        )
        self._ensure_user_exists(db=db, user_id=target_user_id)
        return capture_repository.create(
            db,
            payload.model_copy(update={"user_id": target_user_id}),
        )

    def _resolve_target_user_id(
        self,
        *,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> int:
        target_user_id = requested_user_id or current_user_id
        if requested_user_id is not None and requested_user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return target_user_id

    def _ensure_user_exists(self, *, db: Session, user_id: int) -> None:
        user = users_repository.get_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")


capture_application_service = CaptureApplicationService()
