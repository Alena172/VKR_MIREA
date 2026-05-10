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
    UserCreate,
    UserRead,
)
from app.modules.identity.service import IdentityService

router = APIRouter()


@router.post("/auth/register", response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    service: IdentityService = Depends(),
) -> AuthResponse:
    return service.register(payload)


@router.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    service: IdentityService = Depends(),
) -> AuthResponse:
    return service.login(payload)


@router.post("/auth/token", response_model=TokenResponse)
def token(
    payload: TokenRequest,
    service: IdentityService = Depends(),
) -> TokenResponse:
    return service.issue_token_for_email(email=str(payload.email), password=payload.password)


@router.post("/auth/login-or-register", response_model=LoginOrRegisterResponse)
def login_or_register(
    payload: LoginOrRegisterRequest,
    service: IdentityService = Depends(),
) -> LoginOrRegisterResponse:
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
    return service.verify_token_payload(payload.token)


@router.get("/auth/me", response_model=TokenIdentityResponse)
def me(
    user_id: int = Depends(get_current_user_id),
    service: IdentityService = Depends(),
) -> TokenIdentityResponse:
    return service.get_identity_by_user_id(user_id=user_id)


@router.get("/auth/ping")
def ping() -> dict[str, str]:
    return {"module": "auth", "status": "ok"}


@router.get("/users", response_model=list[UserRead])
def list_users(service: IdentityService = Depends()) -> list[UserRead]:
    return [UserRead.model_validate(user) for user in service.list_user_dtos()]


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    service: IdentityService = Depends(),
) -> UserRead:
    return UserRead.model_validate(service.get_user_or_404(user_id=user_id))


@router.post("/users", response_model=UserRead)
def create_user_endpoint(
    payload: UserCreate,
    service: IdentityService = Depends(),
) -> UserRead:
    return UserRead.model_validate(service.create_user(payload))
