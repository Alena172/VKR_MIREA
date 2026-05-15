"""Удалить устаревшую колонку word из word_progress (заменена на vocabulary_id)

Revision ID: 0023_word_progress_drop_word_column
Revises: 0022_collapse_word_senses_into_dictionary
Create Date: 2026-05-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_word_progress_drop_word_column"
down_revision = "0022_collapse_word_senses_into_dictionary"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :t AND column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "word_progress", "word"):
        op.drop_column("word_progress", "word")


def downgrade() -> None:
    op.add_column(
        "word_progress",
        sa.Column("word", sa.String(), nullable=True),
    )
