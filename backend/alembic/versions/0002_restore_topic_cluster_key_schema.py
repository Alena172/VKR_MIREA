"""Restore topic cluster key based schema.

Revision ID: 0002_restore_topic_cluster_key_schema
Revises: 0001_initial_schema
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_restore_topic_cluster_key_schema"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    topic_cluster_columns = {column["name"] for column in inspector.get_columns("topic_clusters")}
    dictionary_columns = {column["name"] for column in inspector.get_columns("dictionary_entries")}

    if "topic_cluster_key" not in dictionary_columns:
        op.add_column("dictionary_entries", sa.Column("topic_cluster_key", sa.String(length=64), nullable=True))

    if "topic_cluster_id" in dictionary_columns and "id" in topic_cluster_columns:
        op.execute(
            sa.text(
                """
                UPDATE dictionary_entries AS de
                SET topic_cluster_key = tc.cluster_key
                FROM topic_clusters AS tc
                WHERE de.topic_cluster_id = tc.id
                  AND de.topic_cluster_key IS NULL
                """
            )
        )
        op.drop_constraint("dictionary_entries_topic_cluster_id_fkey", "dictionary_entries", type_="foreignkey")
        op.drop_index("ix_dictionary_entries_topic_cluster_id", table_name="dictionary_entries")
        op.drop_column("dictionary_entries", "topic_cluster_id")

    dictionary_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("dictionary_entries")}
    if "ix_dictionary_entries_topic_cluster_key" not in dictionary_indexes:
        op.create_index("ix_dictionary_entries_topic_cluster_key", "dictionary_entries", ["topic_cluster_key"])

    if "id" in topic_cluster_columns:
        topic_cluster_pk = inspector.get_pk_constraint("topic_clusters").get("constrained_columns", [])
        if topic_cluster_pk == ["id"]:
            op.drop_constraint("topic_clusters_pkey", "topic_clusters", type_="primary")
            op.create_primary_key("topic_clusters_pkey", "topic_clusters", ["cluster_key"])

        topic_cluster_indexes = {index["name"] for index in inspector.get_indexes("topic_clusters")}
        if "ix_topic_clusters_id" in topic_cluster_indexes:
            op.drop_index("ix_topic_clusters_id", table_name="topic_clusters")
        if "ix_topic_clusters_cluster_key" in topic_cluster_indexes:
            op.drop_index("ix_topic_clusters_cluster_key", table_name="topic_clusters")

        topic_cluster_uniques = {uc["name"] for uc in inspector.get_unique_constraints("topic_clusters")}
        if "uq_topic_cluster_key" in topic_cluster_uniques:
            op.drop_constraint("uq_topic_cluster_key", "topic_clusters", type_="unique")

        op.drop_column("topic_clusters", "id")


def downgrade() -> None:
    op.add_column("topic_clusters", sa.Column("id", sa.Integer(), nullable=True))
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS topic_clusters_id_seq OWNED BY topic_clusters.id"))
    op.execute(sa.text("UPDATE topic_clusters SET id = nextval('topic_clusters_id_seq') WHERE id IS NULL"))
    op.alter_column(
        "topic_clusters",
        "id",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("nextval('topic_clusters_id_seq')"),
    )
    op.drop_constraint("topic_clusters_pkey", "topic_clusters", type_="primary")
    op.create_primary_key("topic_clusters_pkey", "topic_clusters", ["id"])
    op.create_unique_constraint("uq_topic_cluster_key", "topic_clusters", ["cluster_key"])
    op.create_index("ix_topic_clusters_id", "topic_clusters", ["id"])
    op.create_index("ix_topic_clusters_cluster_key", "topic_clusters", ["cluster_key"])

    op.add_column("dictionary_entries", sa.Column("topic_cluster_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE dictionary_entries AS de
            SET topic_cluster_id = tc.id
            FROM topic_clusters AS tc
            WHERE de.topic_cluster_key = tc.cluster_key
              AND de.topic_cluster_id IS NULL
            """
        )
    )
    op.create_foreign_key(
        "dictionary_entries_topic_cluster_id_fkey",
        "dictionary_entries",
        "topic_clusters",
        ["topic_cluster_id"],
        ["id"],
    )
    op.create_index("ix_dictionary_entries_topic_cluster_id", "dictionary_entries", ["topic_cluster_id"])
    op.drop_index("ix_dictionary_entries_topic_cluster_key", table_name="dictionary_entries")
    op.drop_column("dictionary_entries", "topic_cluster_key")
