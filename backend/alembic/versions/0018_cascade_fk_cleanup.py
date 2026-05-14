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


def _replace_single_column_fk(
    *,
    table_name: str,
    local_column: str,
    constraint_name: str,
    referent_table: str,
    referent_column: str,
    ondelete: str | None = None,
) -> None:
    delete_clause = f" ON DELETE {ondelete}" if ondelete else ""
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                rec record;
            BEGIN
                FOR rec IN
                    SELECT tc.constraint_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                     AND tc.table_name = kcu.table_name
                    WHERE tc.table_schema = current_schema()
                      AND tc.table_name = '{table_name}'
                      AND tc.constraint_type = 'FOREIGN KEY'
                      AND kcu.column_name = '{local_column}'
                LOOP
                    EXECUTE format(
                        'ALTER TABLE %I DROP CONSTRAINT %I',
                        '{table_name}',
                        rec.constraint_name
                    );
                END LOOP;

                EXECUTE
                    'ALTER TABLE "{table_name}" '
                    'ADD CONSTRAINT "{constraint_name}" '
                    'FOREIGN KEY ("{local_column}") '
                    'REFERENCES "{referent_table}" ("{referent_column}"){delete_clause}';
            END $$;
            """
        )
    )


def upgrade() -> None:
    # vocabulary_sense_links.vocabulary_item_id → CASCADE при удалении user_vocabulary
    _replace_single_column_fk(
        table_name="vocabulary_sense_links",
        local_column="vocabulary_item_id",
        constraint_name="vocabulary_sense_links_vocabulary_item_id_fkey",
        referent_table="user_vocabulary",
        referent_column="id",
        ondelete="CASCADE",
    )

    # vocabulary_sense_links.word_sense_id → CASCADE при удалении word_senses
    _replace_single_column_fk(
        table_name="vocabulary_sense_links",
        local_column="word_sense_id",
        constraint_name="vocabulary_sense_links_word_sense_id_fkey",
        referent_table="word_senses",
        referent_column="id",
        ondelete="CASCADE",
    )

    # sense_relations.left_sense_id → CASCADE при удалении word_senses
    _replace_single_column_fk(
        table_name="sense_relations",
        local_column="left_sense_id",
        constraint_name="sense_relations_left_sense_id_fkey",
        referent_table="word_senses",
        referent_column="id",
        ondelete="CASCADE",
    )

    # sense_relations.right_sense_id → CASCADE при удалении word_senses
    _replace_single_column_fk(
        table_name="sense_relations",
        local_column="right_sense_id",
        constraint_name="sense_relations_right_sense_id_fkey",
        referent_table="word_senses",
        referent_column="id",
        ondelete="CASCADE",
    )

    # sense_error_events.word_sense_id → SET NULL при удалении word_senses
    _replace_single_column_fk(
        table_name="sense_error_events",
        local_column="word_sense_id",
        constraint_name="sense_error_events_word_sense_id_fkey",
        referent_table="word_senses",
        referent_column="id",
        ondelete="SET NULL",
    )

    # sense_error_events.session_id → SET NULL при удалении learning_sessions
    _replace_single_column_fk(
        table_name="sense_error_events",
        local_column="session_id",
        constraint_name="sense_error_events_session_id_fkey",
        referent_table="learning_sessions",
        referent_column="id",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    _replace_single_column_fk(
        table_name="sense_error_events",
        local_column="session_id",
        constraint_name="sense_error_events_session_id_fkey",
        referent_table="learning_sessions",
        referent_column="id",
        ondelete=None,
    )
    _replace_single_column_fk(
        table_name="sense_error_events",
        local_column="word_sense_id",
        constraint_name="sense_error_events_word_sense_id_fkey",
        referent_table="word_senses",
        referent_column="id",
        ondelete=None,
    )
    _replace_single_column_fk(
        table_name="sense_relations",
        local_column="right_sense_id",
        constraint_name="sense_relations_right_sense_id_fkey",
        referent_table="word_senses",
        referent_column="id",
        ondelete=None,
    )
    _replace_single_column_fk(
        table_name="sense_relations",
        local_column="left_sense_id",
        constraint_name="sense_relations_left_sense_id_fkey",
        referent_table="word_senses",
        referent_column="id",
        ondelete=None,
    )
    _replace_single_column_fk(
        table_name="vocabulary_sense_links",
        local_column="word_sense_id",
        constraint_name="vocabulary_sense_links_word_sense_id_fkey",
        referent_table="word_senses",
        referent_column="id",
        ondelete=None,
    )
    _replace_single_column_fk(
        table_name="vocabulary_sense_links",
        local_column="vocabulary_item_id",
        constraint_name="vocabulary_sense_links_vocabulary_item_id_fkey",
        referent_table="user_vocabulary",
        referent_column="id",
        ondelete=None,
    )
