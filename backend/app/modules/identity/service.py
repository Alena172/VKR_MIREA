from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError  # re-raised from repository
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.identity import repository
from app.modules.identity.schemas import (
    FindOrCreateUserDTO,
    LoginOrRegisterResponse,
    TokenResponse,
    TokenVerifyResponse,
    UserCreate,
    UserDTO,
)

_ALGORITHM = "HS256"
_SETTINGS = get_settings()
_JWT_SECRET = _SETTINGS.jwt_secret
_JWT_ISSUER = _SETTINGS.jwt_issuer
_JWT_TTL_MINUTES = _SETTINGS.jwt_access_ttl_minutes


def create_access_token(user_id: int) -> str:
    """Выпускает JWT с user_id в поле `sub`."""

    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_JWT_TTL_MINUTES)).timestamp()),
        "iss": _JWT_ISSUER,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)


def verify_token(token: str) -> int | None:
    """Проверяет JWT и возвращает user_id или None при любой ошибке."""

    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_ALGORITHM],
            issuer=_JWT_ISSUER,
        )
    except Exception:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        return int(user_id)
    except ValueError:
        return None


def list_user_dtos(db: Session) -> list[UserDTO]:
    return [UserDTO.from_model(user) for user in repository.list_users(db)]


def get_user_by_id(db: Session, user_id: int) -> UserDTO | None:
    user = repository.get_user_by_id(db, user_id)
    return UserDTO.from_model(user) if user is not None else None


def get_user_by_email(db: Session, email: str) -> UserDTO | None:
    user = repository.get_user_by_email(db, email)
    return UserDTO.from_model(user) if user is not None else None


def get_user_or_404(*, db: Session, user_id: int) -> UserDTO:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def create_user(db: Session, payload: UserCreate) -> UserDTO:
    try:
        user = repository.create_user(db, payload)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Email already exists") from None
    return UserDTO.from_model(user)


def issue_token_for_email(*, db: Session, email: str) -> TokenResponse:
    user = get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return TokenResponse(
        access_token=create_access_token(user.id),
        user_id=user.id,
    )


def find_or_create_user(
    *,
    db: Session,
    email: str,
    full_name: str | None,
    cefr_level: str,
) -> FindOrCreateUserDTO:
    user = repository.get_user_by_email(db, email)
    if user is not None:
        return FindOrCreateUserDTO(
            user=UserDTO.from_model(user),
            is_new_user=False,
        )

    created_user = repository.create_user(
        db,
        UserCreate(
            email=email,
            full_name=full_name,
            cefr_level=cefr_level,
        ),
    )
    return FindOrCreateUserDTO(
        user=UserDTO.from_model(created_user),
        is_new_user=True,
    )


def login_or_register(
    *,
    db: Session,
    email: str,
    full_name: str | None,
    cefr_level: str,
) -> LoginOrRegisterResponse:
    result = find_or_create_user(
        db=db,
        email=email,
        full_name=full_name,
        cefr_level=cefr_level,
    )
    return LoginOrRegisterResponse(
        access_token=create_access_token(result.user.id),
        user_id=result.user.id,
        is_new_user=result.is_new_user,
    )


def verify_token_payload(token: str) -> TokenVerifyResponse:
    user_id = verify_token(token)
    return TokenVerifyResponse(valid=user_id is not None, user_id=user_id)
