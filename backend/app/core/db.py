from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Базовый класс для всех SQLAlchemy-моделей приложения."""

    pass


settings = get_settings()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Создает DB-сессию для FastAPI-зависимостей и закрывает ее после запроса."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
