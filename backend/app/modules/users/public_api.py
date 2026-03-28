from __future__ import annotations

from app.modules.users.repository import users_repository
from app.modules.users.schemas import UserCreate

__all__ = [
    "users_public_api",
]


class UsersPublicApi:
    get_by_id = staticmethod(users_repository.get_by_id)
    get_by_email = staticmethod(users_repository.get_by_email)
    create = staticmethod(users_repository.create)

    @staticmethod
    def get_or_404(*, db, user_id: int):
        user = users_repository.get_by_id(db, user_id)
        if user is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="User not found")
        return user

    @staticmethod
    def find_or_create(*, db, email: str, full_name: str, cefr_level: str):
        user = users_repository.get_by_email(db, email)
        if user is not None:
            return user, False
        user = users_repository.create(
            db,
            UserCreate(
                email=email,
                full_name=full_name,
                cefr_level=cefr_level,
            ),
        )
        return user, True


users_public_api = UsersPublicApi()
