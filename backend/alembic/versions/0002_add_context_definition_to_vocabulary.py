"""add context definition to vocabulary

Revision ID: 0002_ctx_def_vocab
Revises: 0001_initial_schema
Create Date: 2026-02-22 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_ctx_def_vocab"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vocabulary_items", sa.Column("context_definition_ru", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("vocabulary_items", "context_definition_ru")
