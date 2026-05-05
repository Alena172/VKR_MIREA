from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.identity.repositories.users_repository import users_repository
from app.modules.identity.schemas.auth_schemas import (
    LoginOrRegisterRequest,
    LoginOrRegisterResponse,
    TokenIdentityResponse,
    TokenRequest,
    TokenResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
)
from app.modules.identity.dependencies import get_current_user_id
from app.modules.identity.schemas.users_schemas import UserCreate, UserRead
from app.modules.identity.services.auth_service import auth_service
from app.modules.identity.public_api import users_public_api


router = APIRouter()


@router.post("/auth/token", response_model=TokenResponse)
def token(payload: TokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = users_public_api.get_by_email(db, payload.email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    token_value = auth_service.create_access_token(user.id)
    return TokenResponse(access_token=token_value, user_id=user.id)


@router.post("/auth/login-or-register", response_model=LoginOrRegisterResponse)
def login_or_register(
    payload: LoginOrRegisterRequest,
    db: Session = Depends(get_db),
) -> LoginOrRegisterResponse:
    result = users_public_api.find_or_create(
        db=db,
        email=payload.email,
        full_name=payload.full_name,
        cefr_level=payload.cefr_level,
    )

    token_value = auth_service.create_access_token(result.user.id)
    return LoginOrRegisterResponse(
        access_token=token_value,
        user_id=result.user.id,
        is_new_user=result.is_new_user,
    )


@router.post("/auth/verify", response_model=TokenVerifyResponse)
def verify(payload: TokenVerifyRequest) -> TokenVerifyResponse:
    user_id = auth_service.verify_token(payload.token)
    return TokenVerifyResponse(valid=user_id is not None, user_id=user_id)


@router.get("/auth/me", response_model=TokenIdentityResponse)
def me(user_id: int = Depends(get_current_user_id)) -> TokenIdentityResponse:
    return TokenIdentityResponse(user_id=user_id)


@router.get("/auth/ping")
def ping() -> dict[str, str]:
    return {"module": "auth", "status": "ok"}


@router.get("/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    return users_repository.list_users(db)


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserRead:
    user = users_repository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/users", response_model=UserRead)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    try:
        return users_repository.create(db, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
