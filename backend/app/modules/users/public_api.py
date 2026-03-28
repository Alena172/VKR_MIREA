from __future__ import annotations

from app.modules.users.assembler import to_find_or_create_user_dto, to_user_dto
from app.modules.users.contracts import FindOrCreateUserDTO, UserDTO
from app.modules.users.repository import users_repository
from app.modules.users.schemas import UserCreate

__all__ = [
    "FindOrCreateUserDTO",
    "UserDTO",
    "users_public_api",
]


class UsersPublicApi:
    @staticmethod
    def get_by_id(db, user_id: int) -> UserDTO | None:
        user = users_repository.get_by_id(db, user_id)
        return to_user_dto(user) if user is not None else None

    @staticmethod
    def get_by_email(db, email: str) -> UserDTO | None:
        user = users_repository.get_by_email(db, email)
        return to_user_dto(user) if user is not None else None

    @staticmethod
    def create(db, payload: UserCreate) -> UserDTO:
        user = users_repository.create(db, payload)
        return to_user_dto(user)

    @staticmethod
    def get_or_404(*, db, user_id: int):
        user = users_repository.get_by_id(db, user_id)
        if user is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="User not found")
        return to_user_dto(user)

    @staticmethod
    def find_or_create(*, db, email: str, full_name: str, cefr_level: str) -> FindOrCreateUserDTO:
        user = users_repository.get_by_email(db, email)
        if user is not None:
            return to_find_or_create_user_dto(user=user, is_new_user=False)
        user = users_repository.create(
            db,
            UserCreate(
                email=email,
                full_name=full_name,
                cefr_level=cefr_level,
            ),
        )
        return to_find_or_create_user_dto(user=user, is_new_user=True)


users_public_api = UsersPublicApi()
