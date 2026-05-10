from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.modules.identity.repository import IdentityRepository
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
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_JWT_TTL_MINUTES)).timestamp()),
        "iss": _JWT_ISSUER,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)


def verify_token(token: str) -> int | None:
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


class IdentityService:
    def __init__(self, repo: IdentityRepository = Depends()) -> None:
        self._repo = repo

    def list_user_dtos(self) -> list[UserDTO]:
        return [UserDTO.from_model(u) for u in self._repo.list_users()]

    def get_user_by_id(self, user_id: int) -> UserDTO | None:
        user = self._repo.get_by_id(user_id)
        return UserDTO.from_model(user) if user is not None else None

    def get_user_by_email(self, email: str) -> UserDTO | None:
        user = self._repo.get_by_email(email)
        return UserDTO.from_model(user) if user is not None else None

    def get_user_or_404(self, *, user_id: int) -> UserDTO:
        user = self.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def create_user(self, payload: UserCreate) -> UserDTO:
        try:
            user = self._repo.create(payload)
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Email already exists") from None
        return UserDTO.from_model(user)

    def issue_token_for_email(self, *, email: str) -> TokenResponse:
        user = self.get_user_by_email(email)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return TokenResponse(
            access_token=create_access_token(user.id),
            user_id=user.id,
        )

    def find_or_create_user(
        self,
        *,
        email: str,
        full_name: str | None,
        cefr_level: str,
    ) -> FindOrCreateUserDTO:
        user = self._repo.get_by_email(email)
        if user is not None:
            return FindOrCreateUserDTO(user=UserDTO.from_model(user), is_new_user=False)
        created = self._repo.create(
            UserCreate(email=email, full_name=full_name, cefr_level=cefr_level)
        )
        return FindOrCreateUserDTO(user=UserDTO.from_model(created), is_new_user=True)

    def login_or_register(
        self,
        *,
        email: str,
        full_name: str | None,
        cefr_level: str,
    ) -> LoginOrRegisterResponse:
        result = self.find_or_create_user(
            email=email, full_name=full_name, cefr_level=cefr_level
        )
        return LoginOrRegisterResponse(
            access_token=create_access_token(result.user.id),
            user_id=result.user.id,
            is_new_user=result.is_new_user,
        )

    def verify_token_payload(self, token: str) -> TokenVerifyResponse:
        user_id = verify_token(token)
        return TokenVerifyResponse(valid=user_id is not None, user_id=user_id)
