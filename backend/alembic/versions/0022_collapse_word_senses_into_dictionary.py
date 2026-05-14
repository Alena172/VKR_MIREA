"""Удаление word_senses, vocabulary_sense_links, sense_relations;
перенос topic_cluster_id в dictionary_entries.

Revision ID: 0022_collapse_word_senses_into_dictionary
Revises: 0021_add_composite_index_word_progress
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_collapse_word_senses_into_dictionary"
down_revision = "0021_add_composite_index_word_progress"
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

    # 1. Добавляем topic_cluster_id в dictionary_entries
    if not _column_exists(bind, "dictionary_entries", "topic_cluster_id"):
        op.add_column(
            "dictionary_entries",
            sa.Column("topic_cluster_id", sa.Integer(), sa.ForeignKey("topic_clusters.id"), nullable=True),
        )
        op.create_index(
            "ix_dictionary_entries_topic_cluster_id",
            "dictionary_entries",
            ["topic_cluster_id"],
        )

    # 2. Переносим topic_cluster_id из word_senses в dictionary_entries
    #    Путь: user_vocabulary → vocabulary_sense_links → word_senses → topic_cluster_id
    #    У одной dictionary_entry может быть несколько user_vocabulary записей с разными sense_links,
    #    берём MIN(word_sense.topic_cluster_id) — достаточно для инференса темы.
    if _table_exists(bind, "vocabulary_sense_links") and _table_exists(bind, "word_senses"):
        bind.execute(sa.text("""
            UPDATE dictionary_entries de
            SET topic_cluster_id = subq.topic_cluster_id
            FROM (
                SELECT
                    uv.entry_id,
                    MIN(ws.topic_cluster_id) AS topic_cluster_id
                FROM vocabulary_sense_links vsl
                JOIN user_vocabulary uv ON uv.id = vsl.vocabulary_item_id
                JOIN word_senses ws ON ws.id = vsl.word_sense_id
                WHERE uv.entry_id IS NOT NULL
                  AND ws.topic_cluster_id IS NOT NULL
                GROUP BY uv.entry_id
            ) subq
            WHERE de.id = subq.entry_id
              AND de.topic_cluster_id IS NULL
        """))

    # 3. Дропаем зависимые таблицы в правильном порядке
    if _table_exists(bind, "sense_relations"):
        op.drop_table("sense_relations")

    if _table_exists(bind, "vocabulary_sense_links"):
        op.drop_table("vocabulary_sense_links")

    if _table_exists(bind, "word_senses"):
        op.drop_table("word_senses")


def downgrade() -> None:
    # Воссоздаём таблицы (без данных — откат частичный)
    op.create_table(
        "word_senses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("english_lemma", sa.String(200), nullable=False),
        sa.Column("semantic_key", sa.String(120), nullable=False),
        sa.Column("russian_translation", sa.String(200), nullable=False),
        sa.Column("context_definition_ru", sa.Text(), nullable=True),
        sa.Column("topic_cluster_id", sa.Integer(), sa.ForeignKey("topic_clusters.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_word_senses_id", "word_senses", ["id"])
    op.create_index("ix_word_senses_english_lemma", "word_senses", ["english_lemma"])
    op.create_index("ix_word_senses_semantic_key", "word_senses", ["semantic_key"])
    op.create_index("ix_word_senses_topic_cluster_id", "word_senses", ["topic_cluster_id"])
    op.create_unique_constraint("uq_word_sense_lemma_key", "word_senses", ["english_lemma", "semantic_key"])

    op.create_table(
        "vocabulary_sense_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vocabulary_item_id", sa.Integer(), sa.ForeignKey("user_vocabulary.id", ondelete="CASCADE"), nullable=False),
        sa.Column("word_sense_id", sa.Integer(), sa.ForeignKey("word_senses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_vocabulary_sense_links_id", "vocabulary_sense_links", ["id"])
    op.create_index("ix_vocabulary_sense_links_vocabulary_item_id", "vocabulary_sense_links", ["vocabulary_item_id"])
    op.create_index("ix_vocabulary_sense_links_word_sense_id", "vocabulary_sense_links", ["word_sense_id"])
    op.create_unique_constraint("uq_vocab_sense_link_vocab", "vocabulary_sense_links", ["vocabulary_item_id"])

    op.create_table(
        "sense_relations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("left_sense_id", sa.Integer(), sa.ForeignKey("word_senses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("right_sense_id", sa.Integer(), sa.ForeignKey("word_senses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sense_relations_id", "sense_relations", ["id"])
    op.create_index("ix_sense_relations_left_sense_id", "sense_relations", ["left_sense_id"])
    op.create_index("ix_sense_relations_right_sense_id", "sense_relations", ["right_sense_id"])
    op.create_unique_constraint("uq_sense_relation_pair", "sense_relations", ["left_sense_id", "right_sense_id"])

    op.drop_index("ix_dictionary_entries_topic_cluster_id", table_name="dictionary_entries")
    op.drop_column("dictionary_entries", "topic_cluster_id")
