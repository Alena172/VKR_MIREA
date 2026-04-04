"""add vocabulary definition metadata

Revision ID: 0006_vocabulary_definition_metadata
Revises: 0005_base_lexicon
Create Date: 2026-04-04 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_vocabulary_definition_metadata"
down_revision: Union[str, None] = "0005_base_lexicon"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vocabulary_items",
        sa.Column("context_definition_source", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "vocabulary_items",
        sa.Column("context_definition_confidence", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "vocabulary_items",
        sa.Column("definition_reused_from_item_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_vocabulary_items_definition_reused_from_item_id"),
        "vocabulary_items",
        ["definition_reused_from_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_vocabulary_items_definition_reused_from_item_id"),
        table_name="vocabulary_items",
    )
    op.drop_column("vocabulary_items", "definition_reused_from_item_id")
    op.drop_column("vocabulary_items", "context_definition_confidence")
    op.drop_column("vocabulary_items", "context_definition_source")
