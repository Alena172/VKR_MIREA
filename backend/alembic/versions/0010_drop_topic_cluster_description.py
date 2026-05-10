"""drop topic cluster description

Revision ID: 0010_drop_cluster_desc
Revises: 0009_drop_user_contexts
Create Date: 2026-04-07 02:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_drop_cluster_desc"
down_revision: str | None = "0009_drop_user_contexts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("topic_clusters", "description")


def downgrade() -> None:
    op.add_column("topic_clusters", sa.Column("description", sa.Text(), nullable=True))
