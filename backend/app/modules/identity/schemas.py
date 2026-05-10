from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenRequest(BaseModel):
    """Запрос токена для уже существующего пользователя."""

    email: EmailStr


class TokenResponse(BaseModel):
    """Ответ с bearer-токеном и id пользователя."""

    access_token: str
    token_type: str = "bearer"
    user_id: int


class TokenVerifyRequest(BaseModel):
    """Запрос проверки JWT без выполнения защищенного действия."""

    token: str = Field(min_length=10)


class TokenVerifyResponse(BaseModel):
    """Результат проверки JWT."""

    valid: bool
    user_id: int | None = None


class TokenIdentityResponse(BaseModel):
    """Минимальная информация о пользователе из валидного токена."""

    user_id: int


class UserCreate(BaseModel):
    """Данные для создания пользователя."""

    email: EmailStr
    full_name: str | None = Field(default=None, max_length=200)
    cefr_level: str = Field(default="A1", pattern="^(A1|A2|B1|B2|C1|C2)$")


class UserRead(BaseModel):
    """Пользователь в HTTP-ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    cefr_level: str
    created_at: datetime


@dataclass(frozen=True)
class UserDTO:
    """Публичное представление пользователя для межмодульного обмена."""

    id: int
    email: str
    full_name: str | None
    cefr_level: str
    created_at: datetime

    @staticmethod
    def from_model(user: UserModel) -> UserDTO:
        from app.modules.identity.models import UserModel

        if not isinstance(user, UserModel):
            raise TypeError("UserDTO.from_model expects UserModel")

        return UserDTO(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            cefr_level=user.cefr_level,
            created_at=user.created_at,
        )


@dataclass(frozen=True)
class FindOrCreateUserDTO:
    """Результат сценария входа или регистрации пользователя."""

    user: UserDTO
    is_new_user: bool


class LoginOrRegisterRequest(BaseModel):
    """Запрос входа или регистрации в один шаг."""

    email: EmailStr
    full_name: str | None = Field(default=None, max_length=200)
    cefr_level: str = Field(default="A1", pattern="^(A1|A2|B1|B2|C1|C2)$")


class LoginOrRegisterResponse(TokenResponse):
    """Ответ входа или регистрации с признаком нового пользователя."""

    is_new_user: bool
