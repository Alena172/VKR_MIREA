"""base lexicon foundation

Revision ID: 0005_base_lexicon
Revises: 0004_learning_graph_relations
Create Date: 2026-03-29 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_base_lexicon"
down_revision: Union[str, None] = "0004_learning_graph_relations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "base_lexicon_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("english_lemma", sa.String(length=200), nullable=False),
        sa.Column("russian_translation", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("english_lemma", name="uq_base_lexicon_english_lemma"),
    )
    op.create_index(op.f("ix_base_lexicon_entries_id"), "base_lexicon_entries", ["id"], unique=False)
    op.create_index(
        op.f("ix_base_lexicon_entries_english_lemma"),
        "base_lexicon_entries",
        ["english_lemma"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_base_lexicon_entries_english_lemma"), table_name="base_lexicon_entries")
    op.drop_index(op.f("ix_base_lexicon_entries_id"), table_name="base_lexicon_entries")
    op.drop_table("base_lexicon_entries")
