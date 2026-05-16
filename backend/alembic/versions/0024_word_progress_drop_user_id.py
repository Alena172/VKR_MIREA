"""word_progress: drop redundant user_id column

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-16
"""
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_word_progress_user_vocabulary", table_name="word_progress")
    op.drop_index("ix_word_progress_user_id", table_name="word_progress")
    op.drop_index("ix_word_progress_user_next_review", table_name="word_progress")
    op.drop_column("word_progress", "user_id")
    op.create_unique_constraint("uq_word_progress_vocabulary", "word_progress", ["vocabulary_id"])
    op.create_index("ix_word_progress_next_review_at", "word_progress", ["next_review_at"])


def downgrade() -> None:
    op.drop_index("ix_word_progress_next_review_at", table_name="word_progress")
    op.drop_constraint("uq_word_progress_vocabulary", "word_progress")
    op.add_column(
        "word_progress",
        op.Column("user_id", op.Integer(), nullable=True),
    )
    # Восстанавливаем user_id из user_vocabulary
    op.execute("""
        UPDATE word_progress wp
        SET user_id = uv.user_id
        FROM user_vocabulary uv
        WHERE uv.id = wp.vocabulary_id
    """)
    op.alter_column("word_progress", "user_id", nullable=False)
    op.create_index("ix_word_progress_user_id", "word_progress", ["user_id"])
    op.create_index("ix_word_progress_user_next_review", "word_progress", ["user_id", "next_review_at"])
    op.create_unique_constraint(
        "uq_word_progress_user_vocabulary", "word_progress", ["user_id", "vocabulary_id"]
    )
