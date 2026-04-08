from __future__ import annotations

from app.modules.identity.users.contracts import FindOrCreateUserDTO, UserDTO
from app.modules.identity.users.models import UserModel


def to_user_dto(user: UserModel) -> UserDTO:
    return UserDTO(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        cefr_level=user.cefr_level,
        created_at=user.created_at,
    )


def to_find_or_create_user_dto(*, user: UserModel, is_new_user: bool) -> FindOrCreateUserDTO:
    return FindOrCreateUserDTO(
        user=to_user_dto(user),
        is_new_user=is_new_user,
    )
