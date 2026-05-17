from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db, transaction
from app.modules.identity.models import UserModel
from app.modules.identity.security import normalize_email, verify_password
from app.modules.identity.schemas import UserCreate


class IdentityRepository:
    def __init__(self, db: Session = Depends(get_db)) -> None:
        self._db = db

    def get_by_id(self, user_id: int) -> UserModel | None:
        return self._db.get(UserModel, user_id)

    def get_by_email(self, email: str) -> UserModel | None:
        query = select(UserModel).where(UserModel.email == normalize_email(email))
        return self._db.scalar(query)

    def create(self, payload: UserCreate, *, password_hash: str | None) -> UserModel:
        """Создает пользователя; при занятом email наружу поднимется `IntegrityError`."""
        user = UserModel(
            email=normalize_email(str(payload.email)),
            full_name=payload.full_name,
            password_hash=password_hash,
            cefr_level=payload.cefr_level,
        )
        self._db.add(user)
        with transaction(self._db):
            pass
        self._db.refresh(user)
        return user

    def update_cefr_level(self, *, user_id: int, cefr_level: str) -> UserModel | None:
        user = self.get_by_id(user_id)
        if user is None:
            return None
        user.cefr_level = cefr_level
        with transaction(self._db):
            pass
        self._db.refresh(user)
        return user

    def authenticate(self, *, email: str, password: str) -> UserModel | None:
        """Возвращает модель если пароль верный, иначе None."""
        user = self.get_by_email(email)
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
