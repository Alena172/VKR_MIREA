from __future__ import annotations

from contextlib import contextmanager

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.users.repository import users_repository


class AsyncTaskResponse(BaseModel):
    task_id: str
    status: str = "PENDING"
    message: str = "Task queued. Poll /api/v1/tasks/{task_id} for result."


class ApplicationAccess:
    def resolve_target_user_id(
        self,
        *,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> int:
        target_user_id = requested_user_id or current_user_id
        if requested_user_id is not None and requested_user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return target_user_id

    def ensure_user_exists(self, *, db: Session, user_id: int) -> None:
        user = users_repository.get_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

    def get_user_or_404(self, *, db: Session, user_id: int):
        user = users_repository.get_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user


application_access = ApplicationAccess()


class ApplicationTransaction:
    @contextmanager
    def boundary(self, *, db: Session):
        try:
            yield
            db.commit()
        except Exception:
            db.rollback()
            raise


application_transaction = ApplicationTransaction()
