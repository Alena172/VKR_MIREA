"""align practical schema constraints

Revision ID: 0011_align_schema_constraints
Revises: 0010_drop_topic_cluster_description
Create Date: 2026-04-08 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011_align_schema_constraints"
down_revision: Union[str, None] = "0010_drop_topic_cluster_description"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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

    op.create_index(
        "uq_learning_session_answers_session_exercise",
        "learning_session_answers",
        ["session_id", "exercise_id"],
        unique=True,
    )

    op.create_index(
        op.f("ix_user_interests_interest_key"),
        "user_interests",
        ["interest_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_topic_clusters_cluster_key"),
        "topic_clusters",
        ["cluster_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mistake_events_mistake_tag"),
        "mistake_events",
        ["mistake_tag"],
        unique=False,
    )


def downgrade() -> None:
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
