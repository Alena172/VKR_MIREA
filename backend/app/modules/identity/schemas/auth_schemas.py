from pydantic import BaseModel, EmailStr, Field


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


class LoginOrRegisterRequest(BaseModel):
    """Запрос входа или регистрации в один шаг."""

    email: EmailStr
    full_name: str | None = Field(default=None, max_length=200)
    cefr_level: str = Field(default="A1", pattern="^(A1|A2|B1|B2|C1|C2)$")


class LoginOrRegisterResponse(TokenResponse):
    """Ответ входа или регистрации с признаком нового пользователя."""

    is_new_user: bool
