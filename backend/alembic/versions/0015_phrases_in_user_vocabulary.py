"""Фразы в `user_vocabulary`: nullable `entry_id` и колонки `phrase_en/phrase_ru`

Revision ID: 0015_phrases_in_user_vocabulary
Revises: 0014_add_user_password_hash
Create Date: 2026-05-10 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015_phrases_in_user_vocabulary"
down_revision = "0014_add_user_password_hash"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t AND column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar() is not None


def _constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_schema = current_schema() AND table_name = :t AND constraint_name = :c"
        ),
        {"t": table_name, "c": constraint_name},
    )
    return result.scalar() is not None


def _index_exists(bind, index_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = current_schema() AND indexname = :i"
        ),
        {"i": index_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Добавляем колонку `phrase_en`.
    if not _column_exists(bind, "user_vocabulary", "phrase_en"):
        op.add_column(
            "user_vocabulary",
            sa.Column("phrase_en", sa.String(length=500), nullable=True),
        )

    # 2. Добавляем колонку `phrase_ru`.
    if not _column_exists(bind, "user_vocabulary", "phrase_ru"):
        op.add_column(
            "user_vocabulary",
            sa.Column("phrase_ru", sa.String(length=500), nullable=True),
        )

    # 3. Делаем `entry_id` nullable.
    op.alter_column("user_vocabulary", "entry_id", existing_type=sa.Integer(), nullable=True)

    # 4. CHECK-ограничение: должен быть заполнен либо `entry_id`, либо `phrase_en`.
    if not _constraint_exists(bind, "user_vocabulary", "ck_user_vocabulary_word_or_phrase"):
        op.create_check_constraint(
            "ck_user_vocabulary_word_or_phrase",
            "user_vocabulary",
            "(entry_id IS NOT NULL) OR (phrase_en IS NOT NULL)",
        )

    # 5. Уникальное ограничение для фраз: `(user_id, phrase_en)`.
    if not _constraint_exists(bind, "user_vocabulary", "uq_user_vocabulary_user_phrase"):
        op.create_unique_constraint(
            "uq_user_vocabulary_user_phrase",
            "user_vocabulary",
            ["user_id", "phrase_en"],
        )

    # 6. Индекс на `phrase_en` для поиска.
    if not _index_exists(bind, "ix_user_vocabulary_phrase_en"):
        op.create_index(
            "ix_user_vocabulary_phrase_en",
            "user_vocabulary",
            ["phrase_en"],
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _index_exists(bind, "ix_user_vocabulary_phrase_en"):
        op.drop_index("ix_user_vocabulary_phrase_en", table_name="user_vocabulary")

    if _constraint_exists(bind, "user_vocabulary", "uq_user_vocabulary_user_phrase"):
        op.drop_constraint("uq_user_vocabulary_user_phrase", "user_vocabulary", type_="unique")

    if _constraint_exists(bind, "user_vocabulary", "ck_user_vocabulary_word_or_phrase"):
        op.drop_constraint("ck_user_vocabulary_word_or_phrase", "user_vocabulary", type_="check")

    if _column_exists(bind, "user_vocabulary", "phrase_ru"):
        op.drop_column("user_vocabulary", "phrase_ru")

    if _column_exists(bind, "user_vocabulary", "phrase_en"):
        op.drop_column("user_vocabulary", "phrase_en")

    # Возвращаем `NOT NULL`: на этом этапе у всех строк снова должен быть `entry_id`.
    op.alter_column("user_vocabulary", "entry_id", existing_type=sa.Integer(), nullable=False)
