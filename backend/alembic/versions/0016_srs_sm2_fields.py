"""Добавить поля SM-2 (`ease_factor`, `interval_days`) в `word_progress`

Revision ID: 0016_srs_sm2_fields
Revises: 0015_phrases_in_user_vocabulary
Create Date: 2026-05-11 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0016_srs_sm2_fields"
down_revision = "0015_phrases_in_user_vocabulary"
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


def upgrade() -> None:
    bind = op.get_bind()

    if not _column_exists(bind, "word_progress", "ease_factor"):
        op.add_column(
            "word_progress",
            sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
        )

    if not _column_exists(bind, "word_progress", "interval_days"):
        op.add_column(
            "word_progress",
            sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _column_exists(bind, "word_progress", "interval_days"):
        op.drop_column("word_progress", "interval_days")

    if _column_exists(bind, "word_progress", "ease_factor"):
        op.drop_column("word_progress", "ease_factor")
