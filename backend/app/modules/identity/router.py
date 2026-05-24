"""HTTP-эндпоинты аутентификации и профиля текущего пользователя."""

from fastapi import APIRouter, Depends

from app.modules.identity.deps import get_current_user_id
from app.modules.identity.schemas import (
    AuthResponse,
    LoginRequest,
    LoginOrRegisterRequest,
    LoginOrRegisterResponse,
    RegisterRequest,
    TokenIdentityResponse,
    TokenRequest,
    TokenResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
    UpdateMeRequest,
    UpdateMeResponse,
)
from app.modules.identity.service import IdentityService

router = APIRouter(tags=["identity"])


@router.post("/auth/register", response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    service: IdentityService = Depends(),
) -> AuthResponse:
    """Регистрирует пользователя и сразу возвращает access token."""
    return service.register(payload)


@router.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    service: IdentityService = Depends(),
) -> AuthResponse:
    """Аутентифицирует пользователя по email и паролю."""
    return service.login(payload)


@router.post("/auth/token", response_model=TokenResponse)
def token(
    payload: TokenRequest,
    service: IdentityService = Depends(),
) -> TokenResponse:
    """Выдаёт JWT-токен в формате, удобном для простых клиентов и интеграций."""
    return service.issue_token_for_email(email=str(payload.email), password=payload.password)


@router.post("/auth/login-or-register", response_model=LoginOrRegisterResponse)
def login_or_register(
    payload: LoginOrRegisterRequest,
    service: IdentityService = Depends(),
) -> LoginOrRegisterResponse:
    """Логинит существующего пользователя или создаёт нового одним запросом."""
    return service.login_or_register(
        email=str(payload.email),
        full_name=payload.full_name,
        password=payload.password,
        cefr_level=payload.cefr_level,
    )


@router.post("/auth/verify", response_model=TokenVerifyResponse)
def verify(
    payload: TokenVerifyRequest,
    service: IdentityService = Depends(),
) -> TokenVerifyResponse:
    """Проверяет валидность JWT и, если возможно, извлекает `user_id`."""
    return service.verify_token_payload(payload.token)


@router.get("/auth/me", response_model=TokenIdentityResponse)
def me(
    user_id: int = Depends(get_current_user_id),
    service: IdentityService = Depends(),
) -> TokenIdentityResponse:
    """Возвращает профиль пользователя, соответствующего текущему токену."""
    return service.get_identity_by_user_id(user_id=user_id)


@router.patch("/auth/me", response_model=UpdateMeResponse)
def update_me(
    payload: UpdateMeRequest,
    user_id: int = Depends(get_current_user_id),
    service: IdentityService = Depends(),
) -> UpdateMeResponse:
    """Обновляет редактируемые поля профиля текущего пользователя."""
    return service.update_me(user_id=user_id, payload=payload)
