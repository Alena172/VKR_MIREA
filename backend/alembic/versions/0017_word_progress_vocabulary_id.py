"""Привязать word_progress к записи словаря (vocabulary_id вместо word-only ключа)

Revision ID: 0017_word_progress_vocabulary_id
Revises: 0016_srs_sm2_fields
Create Date: 2026-05-11 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_word_progress_vocabulary_id"
down_revision = "0016_srs_sm2_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем nullable FK на user_vocabulary.id
    op.add_column(
        "word_progress",
        sa.Column("vocabulary_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_word_progress_vocabulary_id",
        "word_progress",
        "user_vocabulary",
        ["vocabulary_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Заполняем vocabulary_id для существующих записей:
    # ищем последнюю запись user_vocabulary по (user_id, english_lemma)
    op.execute(
        """
        UPDATE word_progress wp
        SET vocabulary_id = (
            SELECT uv.id
            FROM user_vocabulary uv
            JOIN dictionary_entries de ON de.id = uv.entry_id
            WHERE uv.user_id = wp.user_id
              AND de.english_lemma = wp.word
            ORDER BY uv.added_at DESC
            LIMIT 1
        )
        """
    )

    # Удаляем старый unique constraint (user_id, word)
    op.drop_constraint("uq_word_progress_user_word", "word_progress", type_="unique")

    # Добавляем новый unique constraint (user_id, vocabulary_id) — только для не-NULL
    op.create_index(
        "uq_word_progress_user_vocabulary",
        "word_progress",
        ["user_id", "vocabulary_id"],
        unique=True,
        postgresql_where=sa.text("vocabulary_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_word_progress_user_vocabulary", table_name="word_progress")
    op.create_unique_constraint("uq_word_progress_user_word", "word_progress", ["user_id", "word"])
    op.drop_constraint("fk_word_progress_vocabulary_id", "word_progress", type_="foreignkey")
    op.drop_column("word_progress", "vocabulary_id")
