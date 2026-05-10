"""align practical schema constraints

Revision ID: 0011_align_schema_constraints
Revises: 0010_drop_cluster_desc
Create Date: 2026-04-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_align_schema_constraints"
down_revision: str | None = "0010_drop_cluster_desc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        result = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = current_schema()
                  AND tablename = :table_name
                  AND indexname = :index_name
                """
            ),
            {"table_name": table_name, "index_name": index_name},
        )
        return result.scalar() is not None

    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], *, unique: bool) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    op.execute(
        """
        UPDATE vocabulary_items AS vi
        SET definition_reused_from_item_id = NULL
        WHERE definition_reused_from_item_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM vocabulary_items AS parent
              WHERE parent.id = vi.definition_reused_from_item_id
          )
        """
    )

    op.create_foreign_key(
        "fk_vocabulary_definition_reused_from_item",
        "vocabulary_items",
        "vocabulary_items",
        ["definition_reused_from_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        DELETE FROM learning_session_answers
        WHERE id IN (
            SELECT duplicate.id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY session_id, exercise_id
                           ORDER BY id DESC
                       ) AS rn
                FROM learning_session_answers
            ) AS duplicate
            WHERE duplicate.rn > 1
        )
        """
    )

    _create_index_if_missing(
        "uq_learning_session_answers_session_exercise",
        "learning_session_answers",
        ["session_id", "exercise_id"],
        unique=True,
    )
    _create_index_if_missing(
        op.f("ix_user_interests_interest_key"),
        "user_interests",
        ["interest_key"],
        unique=False,
    )
    _create_index_if_missing(
        op.f("ix_topic_clusters_cluster_key"),
        "topic_clusters",
        ["cluster_key"],
        unique=False,
    )
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = 'mistake_events'"
        )
    )
    if result.scalar() is not None:
        _create_index_if_missing(
            op.f("ix_mistake_events_mistake_tag"),
            "mistake_events",
            ["mistake_tag"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = 'mistake_events'"
        )
    )
    if result.scalar() is not None:
        op.drop_index(op.f("ix_mistake_events_mistake_tag"), table_name="mistake_events")
    op.drop_index(op.f("ix_topic_clusters_cluster_key"), table_name="topic_clusters")
    op.drop_index(op.f("ix_user_interests_interest_key"), table_name="user_interests")
    op.drop_index(
        "uq_learning_session_answers_session_exercise",
        table_name="learning_session_answers",
    )
    op.drop_constraint(
        "fk_vocabulary_definition_reused_from_item",
        "vocabulary_items",
        type_="foreignkey",
    )
