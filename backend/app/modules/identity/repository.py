from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.identity.models import UserModel
from app.modules.identity.schemas import UserCreate


class IdentityRepository:
    def __init__(self, db: Session = Depends(get_db)) -> None:
        self._db = db

    def list_users(self) -> list[UserModel]:
        query = select(UserModel).order_by(UserModel.id.desc())
        return list(self._db.scalars(query))

    def get_by_id(self, user_id: int) -> UserModel | None:
        return self._db.get(UserModel, user_id)

    def get_by_email(self, email: str) -> UserModel | None:
        query = select(UserModel).where(UserModel.email == email)
        return self._db.scalar(query)

    def create(self, payload: UserCreate) -> UserModel:
        """Raises IntegrityError if email already taken."""
        user = UserModel(**payload.model_dump())
        self._db.add(user)
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise
        self._db.refresh(user)
        return user
