"""add user password hash

Revision ID: 0014_add_user_password_hash
Revises: 0013_shared_dictionary
Create Date: 2026-05-10 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0014_add_user_password_hash"
down_revision = "0013_shared_dictionary"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t AND column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "users", "password_hash"):
        op.add_column("users", sa.Column("password_hash", sa.String(length=512), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "users", "password_hash"):
        op.drop_column("users", "password_hash")
