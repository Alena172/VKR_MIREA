"""rename mistake events to sense error events

Revision ID: 0012_rename_mistake_events_to_sense_error_events
Revises: 0011_align_schema_constraints
Create Date: 2026-05-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0012_rename_mistake_events_to_sense_error_events"
down_revision = "0011_align_schema_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("mistake_events", "sense_error_events")
    op.drop_index(op.f("ix_mistake_events_id"), table_name="sense_error_events")
    op.drop_index(op.f("ix_mistake_events_user_id"), table_name="sense_error_events")
    op.drop_index(op.f("ix_mistake_events_session_id"), table_name="sense_error_events")
    op.drop_index(op.f("ix_mistake_events_english_lemma"), table_name="sense_error_events")
    op.drop_index(op.f("ix_mistake_events_word_sense_id"), table_name="sense_error_events")
    op.drop_index(op.f("ix_mistake_events_mistake_tag"), table_name="sense_error_events")
    op.drop_index(op.f("ix_mistake_events_created_at"), table_name="sense_error_events")
    op.create_index(op.f("ix_sense_error_events_user_id"), "sense_error_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_sense_error_events_id"), "sense_error_events", ["id"], unique=False)
    op.create_index(op.f("ix_sense_error_events_session_id"), "sense_error_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_sense_error_events_english_lemma"), "sense_error_events", ["english_lemma"], unique=False)
    op.create_index(op.f("ix_sense_error_events_word_sense_id"), "sense_error_events", ["word_sense_id"], unique=False)
    op.create_index(op.f("ix_sense_error_events_mistake_tag"), "sense_error_events", ["mistake_tag"], unique=False)
    op.create_index(op.f("ix_sense_error_events_created_at"), "sense_error_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sense_error_events_created_at"), table_name="sense_error_events")
    op.drop_index(op.f("ix_sense_error_events_mistake_tag"), table_name="sense_error_events")
    op.drop_index(op.f("ix_sense_error_events_word_sense_id"), table_name="sense_error_events")
    op.drop_index(op.f("ix_sense_error_events_english_lemma"), table_name="sense_error_events")
    op.drop_index(op.f("ix_sense_error_events_session_id"), table_name="sense_error_events")
    op.drop_index(op.f("ix_sense_error_events_id"), table_name="sense_error_events")
    op.drop_index(op.f("ix_sense_error_events_user_id"), table_name="sense_error_events")
    op.create_index(op.f("ix_mistake_events_created_at"), "sense_error_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_mistake_events_mistake_tag"), "sense_error_events", ["mistake_tag"], unique=False)
    op.create_index(op.f("ix_mistake_events_word_sense_id"), "sense_error_events", ["word_sense_id"], unique=False)
    op.create_index(op.f("ix_mistake_events_english_lemma"), "sense_error_events", ["english_lemma"], unique=False)
    op.create_index(op.f("ix_mistake_events_session_id"), "sense_error_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_mistake_events_id"), "sense_error_events", ["id"], unique=False)
    op.create_index(op.f("ix_mistake_events_user_id"), "sense_error_events", ["user_id"], unique=False)
    op.rename_table("sense_error_events", "mistake_events")
