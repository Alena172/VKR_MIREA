from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserDTO:
    """Публичное представление пользователя для межмодульного обмена."""

    id: int
    email: str
    full_name: str | None
    cefr_level: str
    created_at: datetime


@dataclass(frozen=True)
class FindOrCreateUserDTO:
    """Результат сценария входа или регистрации пользователя."""

    user: UserDTO
    is_new_user: bool
