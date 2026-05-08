from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models.users_models import UserModel
from app.modules.identity.schemas.users_schemas import UserCreate


class UsersRepository:
    def list_users(self, db: Session) -> list[UserModel]:
        query = select(UserModel).order_by(UserModel.id.desc())
        return list(db.scalars(query))

    def get_by_id(self, db: Session, user_id: int) -> UserModel | None:
        return db.get(UserModel, user_id)

    def get_by_email(self, db: Session, email: str) -> UserModel | None:
        query = select(UserModel).where(UserModel.email == email)
        return db.scalar(query)

    def create(self, db: Session, payload: UserCreate) -> UserModel:
        user = UserModel(**payload.model_dump())
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


users_repository = UsersRepository()
