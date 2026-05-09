from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.core.config import get_settings
from app.core.db import Base
from app.modules.identity.models.users_models import UserModel
from app.modules.review.models import WordProgressModel
from app.modules.training.models import AnswerModel, LearningSessionModel
from app.modules.graph.models import (
    SenseRelationModel,
    SenseErrorEventModel,
    TopicClusterModel,
    UserInterestModel,
    VocabularySenseLinkModel,
    WordSenseModel,
)
from app.modules.vocabulary.models.base_lexicon_models import BaseLexiconEntryModel
from app.modules.vocabulary.models.items_models import VocabularyItemModel

# Register models for metadata discovery.
_ = (
    UserModel,
    VocabularyItemModel,
    BaseLexiconEntryModel,
    WordProgressModel,
    LearningSessionModel,
    AnswerModel,
    UserInterestModel,
    TopicClusterModel,
    WordSenseModel,
    VocabularySenseLinkModel,
    SenseRelationModel,
    SenseErrorEventModel,
)

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def ensure_alembic_version_column_width(connection) -> None:
    # Older databases may have alembic_version.version_num limited to varchar(32),
    # while our revision identifiers are longer. Widen it before Alembic updates
    # the version row during migration.
    if connection.dialect.name != "postgresql":
        return

    connection.execute(
        text(
            """
            ALTER TABLE IF EXISTS alembic_version
            ALTER COLUMN version_num TYPE VARCHAR(128)
            """
        )
    )


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        ensure_alembic_version_column_width(connection)
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
