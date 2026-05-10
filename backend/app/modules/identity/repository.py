from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.models import UserModel
from app.modules.identity.schemas import UserCreate


def list_users(db: Session) -> list[UserModel]:
    """Возвращает пользователей от новых к старым."""

    query = select(UserModel).order_by(UserModel.id.desc())
    return list(db.scalars(query))


def get_user_by_id(db: Session, user_id: int) -> UserModel | None:
    """Возвращает пользователя по первичному ключу."""

    return db.get(UserModel, user_id)


def get_user_by_email(db: Session, email: str) -> UserModel | None:
    """Возвращает пользователя по уникальному email."""

    query = select(UserModel).where(UserModel.email == email)
    return db.scalar(query)


def create_user(db: Session, payload: UserCreate) -> UserModel:
    """Создает пользователя и сразу фиксирует транзакцию.

    Raises DuplicateEmailError если email уже занят.
    """
    user = UserModel(**payload.model_dump())
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)
    return user
