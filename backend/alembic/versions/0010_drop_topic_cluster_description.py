"""drop topic cluster description

Revision ID: 0010_drop_topic_cluster_description
Revises: 0009_drop_user_contexts
Create Date: 2026-04-07 02:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0010_drop_topic_cluster_description"
down_revision: Union[str, None] = "0009_drop_user_contexts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("topic_clusters", "description")


def downgrade() -> None:
    op.add_column("topic_clusters", sa.Column("description", sa.Text(), nullable=True))
