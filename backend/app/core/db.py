"""Базовая конфигурация SQLAlchemy и короткие транзакционные помощники."""

from collections.abc import Generator
from contextlib import contextmanager

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
    """Открывает сессию БД на время запроса и завершает транзакцию по итогам обработки."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def transaction(db: Session):
    """Оборачивает несколько изменений в одну атомарную транзакцию."""
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise
