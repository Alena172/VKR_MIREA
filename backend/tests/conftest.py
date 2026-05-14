import os
from collections.abc import Generator

os.environ.setdefault("TRUSTED_HOSTS", "localhost,127.0.0.1,backend,gateway,testserver,*.ngrok-free.dev")
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
