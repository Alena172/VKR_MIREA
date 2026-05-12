"""Добавить CASCADE на FK для sense_relations, vocabulary_sense_links, sense_error_events

Revision ID: 0018_cascade_fk_cleanup
Revises: 0017_word_progress_vocabulary_id
Create Date: 2026-05-12 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_cascade_fk_cleanup"
down_revision = "0017_word_progress_vocabulary_id"
branch_labels = None
depends_on = None


def _constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_schema = current_schema() "
            "AND table_name = :t AND constraint_name = :c"
        ),
        {"t": table_name, "c": constraint_name},
    )
    return result.scalar() is not None


def _drop_fk_for_columns(bind, table_name: str, columns: list[str]) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
             AND tc.table_name = kcu.table_name
            WHERE tc.table_schema = current_schema()
              AND tc.table_name = :table_name
              AND tc.constraint_type = 'FOREIGN KEY'
            GROUP BY tc.constraint_name
            HAVING array_agg(kcu.column_name ORDER BY kcu.ordinal_position) = :columns
            """
        ),
        {"table_name": table_name, "columns": columns},
    ).fetchall()
    for (constraint_name,) in rows:
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def _replace_fk(
    bind,
    *,
    table_name: str,
    constraint_name: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    ondelete: str | None = None,
) -> None:
    _drop_fk_for_columns(bind, table_name, local_cols)
    if _constraint_exists(bind, table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
    op.create_foreign_key(
        constraint_name,
        table_name,
        referent_table,
        local_cols,
        remote_cols,
        ondelete=ondelete,
    )


def upgrade() -> None:
    bind = op.get_bind()

    # vocabulary_sense_links.vocabulary_item_id → CASCADE при удалении user_vocabulary
    _replace_fk(
        bind,
        table_name="vocabulary_sense_links",
        constraint_name="vocabulary_sense_links_vocabulary_item_id_fkey",
        referent_table="user_vocabulary",
        local_cols=["vocabulary_item_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )

    # vocabulary_sense_links.word_sense_id → CASCADE при удалении word_senses
    _replace_fk(
        bind,
        table_name="vocabulary_sense_links",
        constraint_name="vocabulary_sense_links_word_sense_id_fkey",
        referent_table="word_senses",
        local_cols=["word_sense_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )

    # sense_relations.left_sense_id → CASCADE при удалении word_senses
    _replace_fk(
        bind,
        table_name="sense_relations",
        constraint_name="sense_relations_left_sense_id_fkey",
        referent_table="word_senses",
        local_cols=["left_sense_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )

    # sense_relations.right_sense_id → CASCADE при удалении word_senses
    _replace_fk(
        bind,
        table_name="sense_relations",
        constraint_name="sense_relations_right_sense_id_fkey",
        referent_table="word_senses",
        local_cols=["right_sense_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )

    # sense_error_events.word_sense_id → SET NULL при удалении word_senses
    _replace_fk(
        bind,
        table_name="sense_error_events",
        constraint_name="sense_error_events_word_sense_id_fkey",
        referent_table="word_senses",
        local_cols=["word_sense_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )

    # sense_error_events.session_id → SET NULL при удалении learning_sessions
    _replace_fk(
        bind,
        table_name="sense_error_events",
        constraint_name="sense_error_events_session_id_fkey",
        referent_table="learning_sessions",
        local_cols=["session_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()

    _replace_fk(
        bind,
        table_name="sense_error_events",
        constraint_name="sense_error_events_session_id_fkey",
        referent_table="learning_sessions",
        local_cols=["session_id"],
        remote_cols=["id"],
        ondelete=None,
    )
    _replace_fk(
        bind,
        table_name="sense_error_events",
        constraint_name="sense_error_events_word_sense_id_fkey",
        referent_table="word_senses",
        local_cols=["word_sense_id"],
        remote_cols=["id"],
        ondelete=None,
    )
    _replace_fk(
        bind,
        table_name="sense_relations",
        constraint_name="sense_relations_right_sense_id_fkey",
        referent_table="word_senses",
        local_cols=["right_sense_id"],
        remote_cols=["id"],
        ondelete=None,
    )
    _replace_fk(
        bind,
        table_name="sense_relations",
        constraint_name="sense_relations_left_sense_id_fkey",
        referent_table="word_senses",
        local_cols=["left_sense_id"],
        remote_cols=["id"],
        ondelete=None,
    )
    _replace_fk(
        bind,
        table_name="vocabulary_sense_links",
        constraint_name="vocabulary_sense_links_word_sense_id_fkey",
        referent_table="word_senses",
        local_cols=["word_sense_id"],
        remote_cols=["id"],
        ondelete=None,
    )
    _replace_fk(
        bind,
        table_name="vocabulary_sense_links",
        constraint_name="vocabulary_sense_links_vocabulary_item_id_fkey",
        referent_table="user_vocabulary",
        local_cols=["vocabulary_item_id"],
        remote_cols=["id"],
        ondelete=None,
    )
