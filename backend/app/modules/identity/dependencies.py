"""Зависимости FastAPI для авторизации пользователя."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.identity.services.auth_service import auth_service

# Сами возвращаем 401, чтобы ответы для отсутствующего и неверного токена были едиными.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int:
    """Возвращает id пользователя из `Authorization: Bearer <token>`.

    Если токен отсутствует или не проходит проверку, прерывает запрос с `401`.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing token")

    user_id = auth_service.verify_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user_id
