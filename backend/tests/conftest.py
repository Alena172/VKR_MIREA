import os
from collections.abc import Generator

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("AI_PROVIDER", "stub")
os.environ.setdefault("AI_BASE_URL", "https://api.openai.com/v1")
os.environ.setdefault("AI_MODEL", "gpt-4o-mini")
os.environ.setdefault("JWT_SECRET", "test_secret_key_that_is_long_enough_12345")
os.environ.setdefault("JWT_ISSUER", "vkr-test")
os.environ.setdefault("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:8080")
os.environ.setdefault("TRUSTED_HOSTS", "localhost,127.0.0.1,backend,gateway,testserver")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
os.environ.setdefault("LIBRETRANSLATE_URL", "http://localhost:5000")
os.environ.setdefault("BOOTSTRAP_SCHEMA_ON_STARTUP", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.modules.identity.models import UserModel
from app.modules.training.models import LearningSessionModel
from app.modules.vocabulary.models import (
    DictionaryEntryModel,
    UserVocabularyModel,
)

# Сохраняем импорты, чтобы SQLAlchemy зарегистрировал metadata всех моделей.
_ = (UserModel, DictionaryEntryModel, UserVocabularyModel, LearningSessionModel)


test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def prepare_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture()
def client() -> TestClient:
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
