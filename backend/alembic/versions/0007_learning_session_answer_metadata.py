"""add structured learning session answer metadata

Revision ID: 0007_learning_session_answer_metadata
Revises: 0006_vocabulary_definition_metadata
Create Date: 2026-04-07 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007_learning_session_answer_metadata"
down_revision: Union[str, None] = "0006_vocabulary_definition_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learning_session_answers",
        sa.Column("exercise_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "learning_session_answers",
        sa.Column("target_word", sa.String(length=200), nullable=True),
    )
    op.create_index(
        op.f("ix_learning_session_answers_target_word"),
        "learning_session_answers",
        ["target_word"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_learning_session_answers_target_word"),
        table_name="learning_session_answers",
    )
    op.drop_column("learning_session_answers", "target_word")
    op.drop_column("learning_session_answers", "exercise_type")
