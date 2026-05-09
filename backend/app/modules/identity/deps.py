from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.identity.service import verify_token

# Сами возвращаем 401, чтобы ответы для отсутствующего и неверного токена были едиными.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int:
    """Возвращает id пользователя из `Authorization: Bearer <token>`."""

    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing token")

    user_id = verify_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user_id
