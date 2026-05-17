"""Начальная схема — финальное состояние

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("password_hash", sa.String(512), nullable=True),
        sa.Column("cefr_level", sa.String(2), nullable=False, server_default="A1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "topic_clusters",
        sa.Column("cluster_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cluster_key"),
    )

    op.create_table(
        "dictionary_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("english_lemma", sa.String(200), nullable=False),
        sa.Column("russian_translation", sa.String(200), nullable=False),
        sa.Column("context_definition_ru", sa.Text(), nullable=True),
        sa.Column("topic_cluster_key", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("english_lemma", "russian_translation", name="uq_dictionary_entry_lemma_translation"),
    )
    op.create_index("ix_dictionary_entries_id", "dictionary_entries", ["id"])
    op.create_index("ix_dictionary_entries_english_lemma", "dictionary_entries", ["english_lemma"])
    op.create_index("ix_dictionary_entries_topic_cluster_key", "dictionary_entries", ["topic_cluster_key"])

    op.create_table(
        "user_vocabulary",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=True),
        sa.Column("phrase_en", sa.String(500), nullable=True),
        sa.Column("phrase_ru", sa.String(500), nullable=True),
        sa.Column("source_sentence", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["entry_id"], ["dictionary_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "entry_id", name="uq_user_vocabulary_user_entry"),
        sa.UniqueConstraint("user_id", "phrase_en", name="uq_user_vocabulary_user_phrase"),
        sa.CheckConstraint("entry_id IS NOT NULL OR phrase_en IS NOT NULL", name="ck_user_vocabulary_word_or_phrase"),
    )
    op.create_index("ix_user_vocabulary_id", "user_vocabulary", ["id"])
    op.create_index("ix_user_vocabulary_user_id", "user_vocabulary", ["user_id"])
    op.create_index("ix_user_vocabulary_entry_id", "user_vocabulary", ["entry_id"])
    op.create_index("ix_user_vocabulary_phrase_en", "user_vocabulary", ["phrase_en"])

    op.create_table(
        "word_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vocabulary_id", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=False),
        sa.Column("next_review_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["vocabulary_id"], ["user_vocabulary.id"], ondelete="CASCADE", name="fk_word_progress_vocabulary_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_word_progress_id", "word_progress", ["id"])
    op.create_index("ix_word_progress_vocabulary_id", "word_progress", ["vocabulary_id"])
    op.create_index("ix_word_progress_next_review_at", "word_progress", ["next_review_at"])
    op.create_unique_constraint("uq_word_progress_vocabulary", "word_progress", ["vocabulary_id"])

    op.create_table(
        "learning_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_sessions_id", "learning_sessions", ["id"])
    op.create_index("ix_learning_sessions_user_id", "learning_sessions", ["user_id"])

    op.create_table(
        "learning_session_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("exercise_type", sa.String(64), nullable=True),
        sa.Column("target_word", sa.String(200), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.String(1000), nullable=True),
        sa.Column("user_answer", sa.String(1000), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("explanation_ru", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "exercise_id", name="uq_learning_session_answers_session_exercise"),
    )
    op.create_index("ix_learning_session_answers_id", "learning_session_answers", ["id"])
    op.create_index("ix_learning_session_answers_session_id", "learning_session_answers", ["session_id"])
    op.create_index("ix_learning_session_answers_target_word", "learning_session_answers", ["target_word"])

    op.create_table(
        "user_interests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("interest_key", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "interest_key", name="uq_user_interest_key"),
    )
    op.create_index("ix_user_interests_id", "user_interests", ["id"])
    op.create_index("ix_user_interests_user_id", "user_interests", ["user_id"])
    op.create_index("ix_user_interests_interest_key", "user_interests", ["interest_key"])


def downgrade() -> None:
    op.drop_table("user_interests")
    op.drop_table("learning_session_answers")
    op.drop_table("learning_sessions")
    op.drop_table("word_progress")
    op.drop_table("user_vocabulary")
    op.drop_table("dictionary_entries")
    op.drop_table("topic_clusters")
    op.drop_table("users")
