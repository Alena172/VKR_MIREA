"""drop redundant user_contexts table

Revision ID: 0009_drop_user_contexts
Revises: 0008_remove_capture_and_context_lists
Create Date: 2026-04-07 01:15:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009_drop_user_contexts"
down_revision: Union[str, None] = "0008_remove_capture_and_context_lists"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("user_contexts")


def downgrade() -> None:
    op.create_table(
        "user_contexts",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("cefr_level", sa.String(length=2), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
