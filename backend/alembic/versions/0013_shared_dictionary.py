"""shared dictionary: dictionary_entries + user_vocabulary

Revision ID: 0013_shared_dictionary
Revises: 0012_rename_mistake_events_to_sense_error_events
Create Date: 2026-05-09 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013_shared_dictionary"
down_revision = "0012_rename_mistake_events_to_sense_error_events"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = current_schema() AND table_name = :t"
    ), {"t": table_name})
    return result.scalar() is not None


def _index_exists(bind, index_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT 1 FROM pg_indexes "
        "WHERE schemaname = current_schema() AND indexname = :i"
    ), {"i": index_name})
    return result.scalar() is not None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table_name, "c": column_name})
    return result.scalar() is not None


def _constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.table_constraints "
        "WHERE table_name = :t AND constraint_name = :c"
    ), {"t": table_name, "c": constraint_name})
    return result.scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Create shared dictionary table
    if not _table_exists(bind, "dictionary_entries"):
        op.create_table(
            "dictionary_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("english_lemma", sa.String(length=200), nullable=False),
            sa.Column("russian_translation", sa.String(length=200), nullable=False),
            sa.Column("context_definition_ru", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "english_lemma", "russian_translation",
                name="uq_dictionary_entry_lemma_translation",
            ),
        )
        op.create_index(op.f("ix_dictionary_entries_id"), "dictionary_entries", ["id"], unique=False)
        op.create_index(op.f("ix_dictionary_entries_english_lemma"), "dictionary_entries", ["english_lemma"], unique=False)

    # 2. Create personal vocabulary link table
    if not _table_exists(bind, "user_vocabulary"):
        op.create_table(
            "user_vocabulary",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("source_sentence", sa.Text(), nullable=True),
            sa.Column("source_url", sa.String(length=2000), nullable=True),
            sa.Column("added_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["entry_id"], ["dictionary_entries.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "entry_id", name="uq_user_vocabulary_user_entry"),
        )
        op.create_index(op.f("ix_user_vocabulary_id"), "user_vocabulary", ["id"], unique=False)
        op.create_index(op.f("ix_user_vocabulary_user_id"), "user_vocabulary", ["user_id"], unique=False)
        op.create_index(op.f("ix_user_vocabulary_entry_id"), "user_vocabulary", ["entry_id"], unique=False)

    # 3. Migrate vocabulary_items → dictionary_entries (idempotent via ON CONFLICT).
    if _table_exists(bind, "vocabulary_items"):
        bind.execute(sa.text("""
            INSERT INTO dictionary_entries (english_lemma, russian_translation, context_definition_ru, created_at)
            SELECT DISTINCT ON (english_lemma, russian_translation)
                   english_lemma, russian_translation, context_definition_ru, NOW()
            FROM vocabulary_items
            WHERE context_definition_ru IS NOT NULL
            ORDER BY english_lemma, russian_translation, id DESC
            ON CONFLICT (english_lemma, russian_translation) DO NOTHING
        """))
        bind.execute(sa.text("""
            INSERT INTO dictionary_entries (english_lemma, russian_translation, context_definition_ru, created_at)
            SELECT DISTINCT ON (english_lemma, russian_translation)
                   english_lemma, russian_translation, NULL, NOW()
            FROM vocabulary_items
            ORDER BY english_lemma, russian_translation, id DESC
            ON CONFLICT (english_lemma, russian_translation) DO NOTHING
        """))

        # 4. Migrate user_vocabulary rows (idempotent via ON CONFLICT).
        bind.execute(sa.text("""
            INSERT INTO user_vocabulary (user_id, entry_id, source_sentence, source_url, added_at)
            SELECT DISTINCT ON (vi.user_id, de.id)
                   vi.user_id, de.id, vi.source_sentence, vi.source_url, NOW()
            FROM vocabulary_items vi
            JOIN dictionary_entries de
              ON de.english_lemma = vi.english_lemma
             AND de.russian_translation = vi.russian_translation
            ORDER BY vi.user_id, de.id, vi.id DESC
            ON CONFLICT (user_id, entry_id) DO NOTHING
        """))

        # 5. Rewire vocabulary_sense_links → user_vocabulary.
        if not _column_exists(bind, "vocabulary_sense_links", "user_vocabulary_id"):
            op.add_column(
                "vocabulary_sense_links",
                sa.Column("user_vocabulary_id", sa.Integer(), nullable=True),
            )
            bind.execute(sa.text("""
                UPDATE vocabulary_sense_links vsl
                SET user_vocabulary_id = uv.id
                FROM vocabulary_items vi
                JOIN dictionary_entries de
                  ON de.english_lemma = vi.english_lemma
                 AND de.russian_translation = vi.russian_translation
                JOIN user_vocabulary uv
                  ON uv.user_id = vi.user_id
                 AND uv.entry_id = de.id
                WHERE vsl.vocabulary_item_id = vi.id
            """))
            bind.execute(sa.text(
                "DELETE FROM vocabulary_sense_links WHERE user_vocabulary_id IS NULL"
            ))
            # Deduplicate: keep lowest id per (user_id, user_vocabulary_id) before unique constraint.
            bind.execute(sa.text("""
                DELETE FROM vocabulary_sense_links
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM vocabulary_sense_links
                    GROUP BY user_id, user_vocabulary_id
                )
            """))

        if _constraint_exists(bind, "vocabulary_sense_links", "uq_vocab_sense_link_user_vocab"):
            op.drop_constraint("uq_vocab_sense_link_user_vocab", "vocabulary_sense_links", type_="unique")
        if _index_exists(bind, "ix_vocabulary_sense_links_vocabulary_item_id"):
            op.drop_index(op.f("ix_vocabulary_sense_links_vocabulary_item_id"), table_name="vocabulary_sense_links")
        if _constraint_exists(bind, "vocabulary_sense_links", "vocabulary_sense_links_vocabulary_item_id_fkey"):
            op.drop_constraint("vocabulary_sense_links_vocabulary_item_id_fkey", "vocabulary_sense_links", type_="foreignkey")
        if _column_exists(bind, "vocabulary_sense_links", "vocabulary_item_id"):
            op.drop_column("vocabulary_sense_links", "vocabulary_item_id")

        if _column_exists(bind, "vocabulary_sense_links", "user_vocabulary_id"):
            op.alter_column("vocabulary_sense_links", "user_vocabulary_id", new_column_name="vocabulary_item_id", nullable=False)

        if not _index_exists(bind, "ix_vocabulary_sense_links_vocabulary_item_id"):
            op.create_index(op.f("ix_vocabulary_sense_links_vocabulary_item_id"), "vocabulary_sense_links", ["vocabulary_item_id"], unique=False)
        if not _constraint_exists(bind, "vocabulary_sense_links", "uq_vocab_sense_link_user_vocab"):
            op.create_unique_constraint("uq_vocab_sense_link_user_vocab", "vocabulary_sense_links", ["user_id", "vocabulary_item_id"])
        if not _constraint_exists(bind, "vocabulary_sense_links", "vocabulary_sense_links_vocabulary_item_id_fkey"):
            op.create_foreign_key("vocabulary_sense_links_vocabulary_item_id_fkey", "vocabulary_sense_links", "user_vocabulary", ["vocabulary_item_id"], ["id"])

        # 6. Drop vocabulary_items and its leftover constraints/indexes.
        if _constraint_exists(bind, "vocabulary_items", "fk_vocabulary_definition_reused_from_item"):
            op.drop_constraint("fk_vocabulary_definition_reused_from_item", "vocabulary_items", type_="foreignkey")
        if _column_exists(bind, "vocabulary_items", "definition_reused_from_item_id"):
            if _index_exists(bind, "ix_vocabulary_items_definition_reused_from_item_id"):
                op.drop_index(op.f("ix_vocabulary_items_definition_reused_from_item_id"), table_name="vocabulary_items")
        if _index_exists(bind, "ix_vocabulary_items_english_lemma"):
            op.drop_index(op.f("ix_vocabulary_items_english_lemma"), table_name="vocabulary_items")
        if _index_exists(bind, "ix_vocabulary_items_user_id"):
            op.drop_index(op.f("ix_vocabulary_items_user_id"), table_name="vocabulary_items")
        if _index_exists(bind, "ix_vocabulary_items_id"):
            op.drop_index(op.f("ix_vocabulary_items_id"), table_name="vocabulary_items")
        op.drop_table("vocabulary_items")


def downgrade() -> None:
    # Restore vocabulary_items
    op.create_table(
        "vocabulary_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("english_lemma", sa.String(length=200), nullable=False),
        sa.Column("russian_translation", sa.String(length=200), nullable=False),
        sa.Column("context_definition_ru", sa.Text(), nullable=True),
        sa.Column("context_definition_source", sa.String(length=64), nullable=True),
        sa.Column("context_definition_confidence", sa.String(length=16), nullable=True),
        sa.Column("definition_reused_from_item_id", sa.Integer(), nullable=True),
        sa.Column("source_sentence", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=2000), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vocabulary_items_id"), "vocabulary_items", ["id"], unique=False)
    op.create_index(op.f("ix_vocabulary_items_user_id"), "vocabulary_items", ["user_id"], unique=False)
    op.create_index(op.f("ix_vocabulary_items_english_lemma"), "vocabulary_items", ["english_lemma"], unique=False)
    op.create_index(
        op.f("ix_vocabulary_items_definition_reused_from_item_id"),
        "vocabulary_items",
        ["definition_reused_from_item_id"],
        unique=False,
    )

    bind = op.get_bind()

    # Re-populate vocabulary_items from user_vocabulary + dictionary_entries
    bind.execute(sa.text("""
        INSERT INTO vocabulary_items (user_id, english_lemma, russian_translation, context_definition_ru, source_sentence, source_url)
        SELECT uv.user_id, de.english_lemma, de.russian_translation, de.context_definition_ru,
               uv.source_sentence, uv.source_url
        FROM user_vocabulary uv
        JOIN dictionary_entries de ON de.id = uv.entry_id
    """))

    # Restore vocabulary_sense_links FK back to vocabulary_items
    op.add_column(
        "vocabulary_sense_links",
        sa.Column("old_vocab_item_id", sa.Integer(), nullable=True),
    )
    bind.execute(sa.text("""
        UPDATE vocabulary_sense_links vsl
        SET old_vocab_item_id = vi.id
        FROM user_vocabulary uv
        JOIN dictionary_entries de ON de.id = uv.entry_id
        JOIN vocabulary_items vi ON vi.user_id = uv.user_id
            AND vi.english_lemma = de.english_lemma
            AND vi.russian_translation = de.russian_translation
        WHERE vsl.vocabulary_item_id = uv.id
    """))

    bind.execute(sa.text("DELETE FROM vocabulary_sense_links WHERE old_vocab_item_id IS NULL"))

    op.drop_constraint("uq_vocab_sense_link_user_vocab", "vocabulary_sense_links", type_="unique")
    op.drop_index(op.f("ix_vocabulary_sense_links_vocabulary_item_id"), table_name="vocabulary_sense_links")
    op.drop_constraint("vocabulary_sense_links_vocabulary_item_id_fkey", "vocabulary_sense_links", type_="foreignkey")
    op.drop_column("vocabulary_sense_links", "vocabulary_item_id")

    op.alter_column("vocabulary_sense_links", "old_vocab_item_id", new_column_name="vocabulary_item_id", nullable=False)

    op.create_index(
        op.f("ix_vocabulary_sense_links_vocabulary_item_id"),
        "vocabulary_sense_links",
        ["vocabulary_item_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_vocab_sense_link_user_vocab",
        "vocabulary_sense_links",
        ["user_id", "vocabulary_item_id"],
    )
    op.create_foreign_key(
        "vocabulary_sense_links_vocabulary_item_id_fkey",
        "vocabulary_sense_links",
        "vocabulary_items",
        ["vocabulary_item_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_vocabulary_definition_reused_from_item",
        "vocabulary_items",
        "vocabulary_items",
        ["definition_reused_from_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Drop new tables
    op.drop_index(op.f("ix_user_vocabulary_entry_id"), table_name="user_vocabulary")
    op.drop_index(op.f("ix_user_vocabulary_user_id"), table_name="user_vocabulary")
    op.drop_index(op.f("ix_user_vocabulary_id"), table_name="user_vocabulary")
    op.drop_table("user_vocabulary")

    op.drop_index(op.f("ix_dictionary_entries_english_lemma"), table_name="dictionary_entries")
    op.drop_index(op.f("ix_dictionary_entries_id"), table_name="dictionary_entries")
    op.drop_table("dictionary_entries")
