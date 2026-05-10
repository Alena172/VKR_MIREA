"""remove capture table and context list fields

Revision ID: 0008_rm_capture_ctx_lists
Revises: 0007_session_answer_meta
Create Date: 2026-04-07 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_rm_capture_ctx_lists"
down_revision: str | None = "0007_session_answer_meta"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_contexts") as batch_op:
        batch_op.drop_column("goals")
        batch_op.drop_column("difficult_words")

    op.drop_index(op.f("ix_capture_items_user_id"), table_name="capture_items")
    op.drop_index(op.f("ix_capture_items_id"), table_name="capture_items")
    op.drop_table("capture_items")


def downgrade() -> None:
    op.create_table(
        "capture_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("selected_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=True),
        sa.Column("source_sentence", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_capture_items_id"), "capture_items", ["id"], unique=False)
    op.create_index(op.f("ix_capture_items_user_id"), "capture_items", ["user_id"], unique=False)

    with op.batch_alter_table("user_contexts") as batch_op:
        batch_op.add_column(sa.Column("goals", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("difficult_words", sa.Text(), nullable=False, server_default="[]"))
