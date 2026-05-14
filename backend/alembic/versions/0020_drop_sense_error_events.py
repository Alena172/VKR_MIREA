"""Удаление таблицы sense_error_events — заменена механизмом SM-2 в word_progress

Revision ID: 0020_drop_sense_error_events
Revises: 0019_denormalize_shared_schema
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_drop_sense_error_events"
down_revision = "0019_denormalize_shared_schema"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :t"
        ),
        {"t": table_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "sense_error_events"):
        op.drop_table("sense_error_events")


def downgrade() -> None:
    op.create_table(
        "sense_error_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("learning_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("english_lemma", sa.String(200), nullable=True),
        sa.Column("word_sense_id", sa.Integer(), sa.ForeignKey("word_senses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mistake_tag", sa.String(120), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.String(1000), nullable=True),
        sa.Column("user_answer", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sense_error_events_id", "sense_error_events", ["id"])
    op.create_index("ix_sense_error_events_user_id", "sense_error_events", ["user_id"])
    op.create_index("ix_sense_error_events_session_id", "sense_error_events", ["session_id"])
    op.create_index("ix_sense_error_events_english_lemma", "sense_error_events", ["english_lemma"])
    op.create_index("ix_sense_error_events_word_sense_id", "sense_error_events", ["word_sense_id"])
    op.create_index("ix_sense_error_events_mistake_tag", "sense_error_events", ["mistake_tag"])
    op.create_index("ix_sense_error_events_created_at", "sense_error_events", ["created_at"])
