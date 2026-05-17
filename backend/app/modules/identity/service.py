from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import (
    hash_password,
    make_unusable_password_hash,
    normalize_email,
)
from app.modules.identity.schemas import (
    AuthResponse,
    FindOrCreateUserDTO,
    LoginOrRegisterResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    TokenIdentityResponse,
    TokenVerifyResponse,
    UpdateMeRequest,
    UpdateMeResponse,
    UserCreate,
    UserDTO,
    UserRead,
)

_ALGORITHM = "HS256"


def _jwt_settings():
    from app.core.config import get_settings
    s = get_settings()
    return s.jwt_secret, s.jwt_issuer, s.jwt_access_ttl_minutes


def create_access_token(user_id: int) -> str:
    secret, issuer, ttl_minutes = _jwt_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "iss": issuer,
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def verify_token(token: str) -> int | None:
    secret, issuer, _ = _jwt_settings()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            issuer=issuer,
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

    def get_user_by_id(self, user_id: int) -> UserDTO | None:
        user = self._repo.get_by_id(user_id)
        return UserDTO.from_model(user) if user is not None else None

    def get_user_or_404(self, *, user_id: int) -> UserDTO:
        user = self.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def create_user(self, payload: UserCreate) -> UserDTO:
        try:
            password_hash = (
                hash_password(payload.password)
                if payload.password
                else make_unusable_password_hash()
            )
            user = self._repo.create(payload, password_hash=password_hash)
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Email already exists") from None
        return UserDTO.from_model(user)

    def authenticate_user(self, *, email: str, password: str) -> UserDTO:
        user = self._repo.authenticate(email=normalize_email(email), password=password)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return UserDTO.from_model(user)

    def issue_token_for_email(self, *, email: str, password: str) -> TokenResponse:
        user = self.authenticate_user(email=email, password=password)
        return TokenResponse(access_token=create_access_token(user.id), user_id=user.id)

    def register(self, payload: RegisterRequest) -> AuthResponse:
        user_dto = self.create_user(
            UserCreate(
                email=payload.email,
                full_name=payload.full_name,
                password=payload.password,
                cefr_level=payload.cefr_level,
            )
        )
        return AuthResponse(
            access_token=create_access_token(user_dto.id),
            user_id=user_dto.id,
            user=UserRead.model_validate(user_dto),
        )

    def login(self, payload: LoginRequest) -> AuthResponse:
        user = self.authenticate_user(email=str(payload.email), password=payload.password)
        return AuthResponse(
            access_token=create_access_token(user.id),
            user_id=user.id,
            user=UserRead.model_validate(user),
        )

    def find_or_create_user(
        self,
        *,
        email: str,
        full_name: str | None,
        password: str,
        cefr_level: str,
    ) -> FindOrCreateUserDTO:
        normalized = normalize_email(email)
        existing = self._repo.authenticate(email=normalized, password=password)
        if existing is not None:
            return FindOrCreateUserDTO(user=UserDTO.from_model(existing), is_new_user=False)
        if self._repo.get_by_email(normalized) is not None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        created = self._repo.create(
            UserCreate(email=normalized, full_name=full_name, password=password, cefr_level=cefr_level),
            password_hash=hash_password(password),
        )
        return FindOrCreateUserDTO(user=UserDTO.from_model(created), is_new_user=True)

    def login_or_register(
        self,
        *,
        email: str,
        full_name: str | None,
        password: str,
        cefr_level: str,
    ) -> LoginOrRegisterResponse:
        result = self.find_or_create_user(
            email=email, full_name=full_name, password=password, cefr_level=cefr_level,
        )
        return LoginOrRegisterResponse(
            access_token=create_access_token(result.user.id),
            user_id=result.user.id,
            is_new_user=result.is_new_user,
            user=UserRead.model_validate(result.user),
        )

    def verify_token_payload(self, token: str) -> TokenVerifyResponse:
        user_id = verify_token(token)
        return TokenVerifyResponse(valid=user_id is not None, user_id=user_id)

    def update_me(self, *, user_id: int, payload: UpdateMeRequest) -> UpdateMeResponse:
        user = self._repo.update_cefr_level(user_id=user_id, cefr_level=payload.cefr_level)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return UpdateMeResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            cefr_level=user.cefr_level,
        )

    def get_identity_by_user_id(self, *, user_id: int) -> TokenIdentityResponse:
        user = self.get_user_or_404(user_id=user_id)
        return TokenIdentityResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            cefr_level=user.cefr_level,
        )
