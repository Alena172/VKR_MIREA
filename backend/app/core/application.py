"""Общие DTO и проверки доступа, используемые несколькими модулями."""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session


class AsyncTaskResponse(BaseModel):
    """Стандартный ответ API при постановке операции в фоновую очередь."""

    task_id: str
    status: str = "PENDING"
    message: str = "Task queued. Poll /api/v1/tasks/{task_id} for result."


class ApplicationAccess:
    """Централизует простые cross-module проверки доступа."""

    def resolve_target_user_id(
        self,
        *,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> int:
        """Возвращает целевой `user_id`, не позволяя обращаться к чужим данным."""

        target_user_id = requested_user_id or current_user_id
        if requested_user_id is not None and requested_user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return target_user_id

    def get_user_or_404(self, *, user_id: int, db: Session):
        """Возвращает пользователя из identity-модуля или завершает запрос c `404`."""
        from app.modules.identity.repository import IdentityRepository

        user = IdentityRepository(db).get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user


application_access = ApplicationAccess()
