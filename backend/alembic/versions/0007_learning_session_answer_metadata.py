"""Добавить структурированные metadata ответов учебной сессии

Revision ID: 0007_session_answer_meta
Revises: 0006_vocab_def_meta
Create Date: 2026-04-07 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# Идентификаторы ревизии, которые использует Alembic.
revision: str = "0007_session_answer_meta"
down_revision: str | None = "0006_vocab_def_meta"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_session_answers",
        sa.Column("exercise_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "learning_session_answers",
        sa.Column("target_word", sa.String(length=200), nullable=True),
    )
    op.create_index(
        op.f("ix_learning_session_answers_target_word"),
        "learning_session_answers",
        ["target_word"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_learning_session_answers_target_word"),
        table_name="learning_session_answers",
    )
    op.drop_column("learning_session_answers", "target_word")
    op.drop_column("learning_session_answers", "exercise_type")
