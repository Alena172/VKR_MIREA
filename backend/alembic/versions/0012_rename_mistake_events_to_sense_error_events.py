"""Переименовать mistake events в sense error events

Revision ID: 0012_rename_mistake_events_to_sense_error_events
Revises: 0011_align_schema_constraints
Create Date: 2026-05-03 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_rename_mistake_events_to_sense_error_events"
down_revision = "0011_align_schema_constraints"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = current_schema() AND table_name = :t"
    ), {"t": table_name})
    return result.scalar() is not None


def _index_exists(bind, index_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT 1 FROM pg_indexes "
        "WHERE schemaname = current_schema() AND indexname = :i"
    ), {"i": index_name})
    return result.scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "sense_error_events"):
        # Таблица уже переименована или создана с нуля — проверяем только нужные индексы.
        for idx in [
            "ix_sense_error_events_id", "ix_sense_error_events_user_id",
            "ix_sense_error_events_session_id", "ix_sense_error_events_english_lemma",
            "ix_sense_error_events_word_sense_id", "ix_sense_error_events_mistake_tag",
            "ix_sense_error_events_created_at",
        ]:
            if not _index_exists(bind, idx):
                col = idx.removeprefix("ix_sense_error_events_")
                op.create_index(op.f(idx), "sense_error_events", [col], unique=False)
        return

    if not _table_exists(bind, "mistake_events"):
        # Ни старой, ни новой таблицы нет — создаем `sense_error_events` с нуля.
        op.create_table(
            "sense_error_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=True),
            sa.Column("english_lemma", sa.String(length=200), nullable=True),
            sa.Column("word_sense_id", sa.Integer(), nullable=True),
            sa.Column("mistake_tag", sa.String(length=120), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=True),
            sa.Column("expected_answer", sa.String(length=1000), nullable=True),
            sa.Column("user_answer", sa.String(length=1000), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["word_sense_id"], ["word_senses.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_sense_error_events_id"), "sense_error_events", ["id"], unique=False)
        op.create_index(op.f("ix_sense_error_events_user_id"), "sense_error_events", ["user_id"], unique=False)
        op.create_index(op.f("ix_sense_error_events_session_id"), "sense_error_events", ["session_id"], unique=False)
        op.create_index(op.f("ix_sense_error_events_english_lemma"), "sense_error_events", ["english_lemma"], unique=False)
        op.create_index(op.f("ix_sense_error_events_word_sense_id"), "sense_error_events", ["word_sense_id"], unique=False)
        op.create_index(op.f("ix_sense_error_events_mistake_tag"), "sense_error_events", ["mistake_tag"], unique=False)
        op.create_index(op.f("ix_sense_error_events_created_at"), "sense_error_events", ["created_at"], unique=False)
        return

    # Обычный сценарий: переименовываем `mistake_events` в `sense_error_events`.
    op.rename_table("mistake_events", "sense_error_events")
    for idx in [
        "ix_mistake_events_id", "ix_mistake_events_user_id", "ix_mistake_events_session_id",
        "ix_mistake_events_english_lemma", "ix_mistake_events_word_sense_id",
        "ix_mistake_events_mistake_tag", "ix_mistake_events_created_at",
    ]:
        if _index_exists(bind, idx):
            op.drop_index(op.f(idx), table_name="sense_error_events")
    op.create_index(op.f("ix_sense_error_events_user_id"), "sense_error_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_sense_error_events_id"), "sense_error_events", ["id"], unique=False)
    op.create_index(op.f("ix_sense_error_events_session_id"), "sense_error_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_sense_error_events_english_lemma"), "sense_error_events", ["english_lemma"], unique=False)
    op.create_index(op.f("ix_sense_error_events_word_sense_id"), "sense_error_events", ["word_sense_id"], unique=False)
    op.create_index(op.f("ix_sense_error_events_mistake_tag"), "sense_error_events", ["mistake_tag"], unique=False)
    op.create_index(op.f("ix_sense_error_events_created_at"), "sense_error_events", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    for idx in [
        "ix_sense_error_events_created_at", "ix_sense_error_events_mistake_tag",
        "ix_sense_error_events_word_sense_id", "ix_sense_error_events_english_lemma",
        "ix_sense_error_events_session_id", "ix_sense_error_events_id",
        "ix_sense_error_events_user_id",
    ]:
        if _index_exists(bind, idx):
            op.drop_index(op.f(idx), table_name="sense_error_events")
    op.create_index(op.f("ix_mistake_events_created_at"), "sense_error_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_mistake_events_mistake_tag"), "sense_error_events", ["mistake_tag"], unique=False)
    op.create_index(op.f("ix_mistake_events_word_sense_id"), "sense_error_events", ["word_sense_id"], unique=False)
    op.create_index(op.f("ix_mistake_events_english_lemma"), "sense_error_events", ["english_lemma"], unique=False)
    op.create_index(op.f("ix_mistake_events_session_id"), "sense_error_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_mistake_events_id"), "sense_error_events", ["id"], unique=False)
    op.create_index(op.f("ix_mistake_events_user_id"), "sense_error_events", ["user_id"], unique=False)
    op.rename_table("sense_error_events", "mistake_events")
