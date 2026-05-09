from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.identity.deps import get_current_user_id
from app.modules.identity.schemas import (
    LoginOrRegisterRequest,
    LoginOrRegisterResponse,
    TokenIdentityResponse,
    TokenRequest,
    TokenResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
    UserCreate,
    UserRead,
)
from app.modules.identity.service import (
    create_user,
    get_user_or_404,
    issue_token_for_email,
    login_or_register as login_or_register_user,
    list_user_dtos,
    verify_token_payload,
)

router = APIRouter()


@router.post("/auth/token", response_model=TokenResponse)
def token(payload: TokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return issue_token_for_email(db=db, email=payload.email)


@router.post("/auth/login-or-register", response_model=LoginOrRegisterResponse)
def login_or_register(
    payload: LoginOrRegisterRequest,
    db: Session = Depends(get_db),
) -> LoginOrRegisterResponse:
    return login_or_register_user(
        db=db,
        email=payload.email,
        full_name=payload.full_name,
        cefr_level=payload.cefr_level,
    )


@router.post("/auth/verify", response_model=TokenVerifyResponse)
def verify(payload: TokenVerifyRequest) -> TokenVerifyResponse:
    return verify_token_payload(payload.token)


@router.get("/auth/me", response_model=TokenIdentityResponse)
def me(user_id: int = Depends(get_current_user_id)) -> TokenIdentityResponse:
    return TokenIdentityResponse(user_id=user_id)


@router.get("/auth/ping")
def ping() -> dict[str, str]:
    return {"module": "auth", "status": "ok"}


@router.get("/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    return [UserRead.model_validate(user) for user in list_user_dtos(db)]


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserRead:
    return UserRead.model_validate(get_user_or_404(db=db, user_id=user_id))


@router.post("/users", response_model=UserRead)
def create_user_endpoint(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    return UserRead.model_validate(create_user(db, payload))
