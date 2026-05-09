from __future__ import annotations

from contextlib import contextmanager

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.identity.repositories.users_repository import users_repository


class AsyncTaskResponse(BaseModel):
    """Единый ответ для операций, которые ставятся в фоновую очередь."""

    task_id: str
    status: str = "PENDING"
    message: str = "Task queued. Poll /api/v1/tasks/{task_id} for result."


class ApplicationAccess:
    """Общие проверки доступа, которые используются разными модулями."""

    def resolve_target_user_id(
        self,
        *,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> int:
        """Возвращает разрешенный user_id и запрещает доступ к чужим данным."""

        target_user_id = requested_user_id or current_user_id
        if requested_user_id is not None and requested_user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return target_user_id

    def get_user_or_404(self, *, db: Session, user_id: int):
        """Возвращает пользователя или останавливает HTTP-запрос с 404."""

        user = users_repository.get_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user


application_access = ApplicationAccess()


class ApplicationTransaction:
    """Единая транзакционная граница для application-сервисов."""

    @contextmanager
    def boundary(self, *, db: Session):
        """Коммитит успешный сценарий и откатывает транзакцию при ошибке."""

        try:
            yield
            db.commit()
        except Exception:
            db.rollback()
            raise


application_transaction = ApplicationTransaction()
