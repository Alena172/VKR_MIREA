"""Добавление составного индекса (user_id, next_review_at) для таблицы word_progress

Revision ID: 0021_add_composite_index_word_progress
Revises: 0020_drop_sense_error_events
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op

revision = "0021_add_composite_index_word_progress"
down_revision = "0020_drop_sense_error_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_word_progress_user_next_review",
        "word_progress",
        ["user_id", "next_review_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_word_progress_user_next_review", table_name="word_progress")
