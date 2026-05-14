"""Денормализация схемы: общие смыслы, кластеры и связи без user_id; удаление base_lexicon; word из word_progress

Revision ID: 0019_denormalize_shared_schema
Revises: 0018_cascade_fk_cleanup
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_denormalize_shared_schema"
down_revision = "0018_cascade_fk_cleanup"
branch_labels = None
depends_on = None


def _constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_schema = current_schema() "
            "AND table_name = :t AND constraint_name = :c"
        ),
        {"t": table_name, "c": constraint_name},
    )
    return result.scalar() is not None


def _index_exists(bind, index_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = current_schema() AND indexname = :n"
        ),
        {"n": index_name},
    )
    return result.scalar() is not None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :t AND column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar() is not None


def _table_exists(bind, table_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :t"
        ),
        {"t": table_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Дропаем base_lexicon_entries — перекрыта dictionary_entries
    # ------------------------------------------------------------------
    if _table_exists(bind, "base_lexicon_entries"):
        op.drop_table("base_lexicon_entries")

    # ------------------------------------------------------------------
    # 2. topic_clusters: убираем user_id, делаем cluster_key глобальным
    #    Алгоритм: оставляем первую запись по каждому cluster_key,
    #    обновляем word_senses.topic_cluster_id на выжившую запись, удаляем дубли.
    # ------------------------------------------------------------------
    if _column_exists(bind, "topic_clusters", "user_id"):
        # Для каждого cluster_key находим минимальный id (survivor) и
        # переводим все ссылки из word_senses на него
        bind.execute(sa.text("""
            UPDATE word_senses ws
            SET topic_cluster_id = survivors.min_id
            FROM (
                SELECT cluster_key, MIN(id) AS min_id
                FROM topic_clusters
                GROUP BY cluster_key
            ) survivors
            JOIN topic_clusters tc ON tc.cluster_key = survivors.cluster_key
            WHERE ws.topic_cluster_id = tc.id
              AND tc.id <> survivors.min_id
        """))

        # Удаляем дублирующиеся кластеры (не-survivors)
        bind.execute(sa.text("""
            DELETE FROM topic_clusters
            WHERE id NOT IN (
                SELECT MIN(id) FROM topic_clusters GROUP BY cluster_key
            )
        """))

        # Теперь можно безопасно снять уникальный constraint на (user_id, cluster_key)
        if _constraint_exists(bind, "topic_clusters", "uq_topic_cluster_user_key"):
            op.drop_constraint("uq_topic_cluster_user_key", "topic_clusters", type_="unique")

        # Добавляем новый уникальный constraint только на cluster_key
        if not _constraint_exists(bind, "topic_clusters", "uq_topic_cluster_key"):
            op.create_unique_constraint("uq_topic_cluster_key", "topic_clusters", ["cluster_key"])

        # Удаляем столбец user_id
        op.drop_column("topic_clusters", "user_id")

    # ------------------------------------------------------------------
    # 3. word_senses: убираем user_id, source_sentence, source_url
    #    Алгоритм: оставляем одну запись по (english_lemma, semantic_key),
    #    обновляем vocabulary_sense_links и sense_error_events на выжившие id.
    # ------------------------------------------------------------------
    if _column_exists(bind, "word_senses", "user_id"):
        # Найти survivor для каждой пары (english_lemma, semantic_key)
        bind.execute(sa.text("""
            UPDATE vocabulary_sense_links vsl
            SET word_sense_id = survivors.min_id
            FROM (
                SELECT english_lemma, semantic_key, MIN(id) AS min_id
                FROM word_senses
                GROUP BY english_lemma, semantic_key
            ) survivors
            JOIN word_senses ws ON ws.english_lemma = survivors.english_lemma
                                AND ws.semantic_key  = survivors.semantic_key
            WHERE vsl.word_sense_id = ws.id
              AND ws.id <> survivors.min_id
        """))

        bind.execute(sa.text("""
            UPDATE sense_error_events see
            SET word_sense_id = survivors.min_id
            FROM (
                SELECT english_lemma, semantic_key, MIN(id) AS min_id
                FROM word_senses
                GROUP BY english_lemma, semantic_key
            ) survivors
            JOIN word_senses ws ON ws.english_lemma = survivors.english_lemma
                                AND ws.semantic_key  = survivors.semantic_key
            WHERE see.word_sense_id = ws.id
              AND ws.id <> survivors.min_id
        """))

        # sense_relations: для дублей обновляем left_sense_id / right_sense_id
        bind.execute(sa.text("""
            UPDATE sense_relations sr
            SET left_sense_id = survivors.min_id
            FROM (
                SELECT english_lemma, semantic_key, MIN(id) AS min_id
                FROM word_senses
                GROUP BY english_lemma, semantic_key
            ) survivors
            JOIN word_senses ws ON ws.english_lemma = survivors.english_lemma
                                AND ws.semantic_key  = survivors.semantic_key
            WHERE sr.left_sense_id = ws.id
              AND ws.id <> survivors.min_id
        """))

        bind.execute(sa.text("""
            UPDATE sense_relations sr
            SET right_sense_id = survivors.min_id
            FROM (
                SELECT english_lemma, semantic_key, MIN(id) AS min_id
                FROM word_senses
                GROUP BY english_lemma, semantic_key
            ) survivors
            JOIN word_senses ws ON ws.english_lemma = survivors.english_lemma
                                AND ws.semantic_key  = survivors.semantic_key
            WHERE sr.right_sense_id = ws.id
              AND ws.id <> survivors.min_id
        """))

        # Удаляем sense_relations, ставшие self-loops после нормализации
        bind.execute(sa.text(
            "DELETE FROM sense_relations WHERE left_sense_id = right_sense_id"
        ))

        # Удаляем дублирующиеся sense_relations (одинаковая пара после merge)
        bind.execute(sa.text("""
            DELETE FROM sense_relations
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM sense_relations
                GROUP BY LEAST(left_sense_id, right_sense_id),
                         GREATEST(left_sense_id, right_sense_id)
            )
        """))

        # Удаляем дублирующиеся word_senses
        bind.execute(sa.text("""
            DELETE FROM word_senses
            WHERE id NOT IN (
                SELECT MIN(id) FROM word_senses GROUP BY english_lemma, semantic_key
            )
        """))

        # Снимаем старый уникальный constraint
        if _constraint_exists(bind, "word_senses", "uq_word_sense_user_lemma_key"):
            op.drop_constraint("uq_word_sense_user_lemma_key", "word_senses", type_="unique")

        # Добавляем новый уникальный constraint
        if not _constraint_exists(bind, "word_senses", "uq_word_sense_lemma_key"):
            op.create_unique_constraint("uq_word_sense_lemma_key", "word_senses", ["english_lemma", "semantic_key"])

        # Удаляем колонки
        op.drop_column("word_senses", "user_id")
        if _column_exists(bind, "word_senses", "source_sentence"):
            op.drop_column("word_senses", "source_sentence")
        if _column_exists(bind, "word_senses", "source_url"):
            op.drop_column("word_senses", "source_url")

    # ------------------------------------------------------------------
    # 4. sense_relations: убираем user_id
    # ------------------------------------------------------------------
    if _column_exists(bind, "sense_relations", "user_id"):
        if _constraint_exists(bind, "sense_relations", "uq_sense_relation_pair"):
            op.drop_constraint("uq_sense_relation_pair", "sense_relations", type_="unique")
        if not _constraint_exists(bind, "sense_relations", "uq_sense_relation_pair"):
            op.create_unique_constraint("uq_sense_relation_pair", "sense_relations", ["left_sense_id", "right_sense_id"])
        op.drop_column("sense_relations", "user_id")

    # ------------------------------------------------------------------
    # 5. vocabulary_sense_links: убираем user_id
    # ------------------------------------------------------------------
    if _column_exists(bind, "vocabulary_sense_links", "user_id"):
        if _constraint_exists(bind, "vocabulary_sense_links", "uq_vocab_sense_link_user_vocab"):
            op.drop_constraint("uq_vocab_sense_link_user_vocab", "vocabulary_sense_links", type_="unique")
        # Удаляем дубликаты по vocabulary_item_id перед созданием уникального ограничения
        bind.execute(sa.text(
            """
            DELETE FROM vocabulary_sense_links
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM vocabulary_sense_links
                GROUP BY vocabulary_item_id
            )
            """
        ))
        if not _constraint_exists(bind, "vocabulary_sense_links", "uq_vocab_sense_link_vocab"):
            op.create_unique_constraint("uq_vocab_sense_link_vocab", "vocabulary_sense_links", ["vocabulary_item_id"])
        op.drop_column("vocabulary_sense_links", "user_id")

    # ------------------------------------------------------------------
    # 6. word_progress: удаляем word, делаем vocabulary_id NOT NULL,
    #    заменяем partial index на обычный уникальный
    # ------------------------------------------------------------------

    # Удаляем записи без vocabulary_id (осиротевшие legacy-строки)
    bind.execute(sa.text(
        "DELETE FROM word_progress WHERE vocabulary_id IS NULL"
    ))

    # Удаляем partial index если существует
    if _index_exists(bind, "uq_word_progress_user_vocabulary"):
        op.drop_index("uq_word_progress_user_vocabulary", table_name="word_progress")

    # Ставим NOT NULL на vocabulary_id
    op.alter_column("word_progress", "vocabulary_id", nullable=False)

    # Создаём обычный уникальный индекс
    op.create_index(
        "uq_word_progress_user_vocabulary",
        "word_progress",
        ["user_id", "vocabulary_id"],
        unique=True,
    )

    # Удаляем поле word
    if _column_exists(bind, "word_progress", "word"):
        op.drop_column("word_progress", "word")


def downgrade() -> None:
    bind = op.get_bind()

    # word_progress: возвращаем поле word
    if not _column_exists(bind, "word_progress", "word"):
        op.add_column("word_progress", sa.Column("word", sa.String(200), nullable=True))
        # Заполняем word из user_vocabulary → dictionary_entries
        bind.execute(sa.text("""
            UPDATE word_progress wp
            SET word = COALESCE(de.english_lemma, uv.phrase_en, 'unknown')
            FROM user_vocabulary uv
            LEFT JOIN dictionary_entries de ON de.id = uv.entry_id
            WHERE uv.id = wp.vocabulary_id
        """))
        op.alter_column("word_progress", "word", nullable=False)

    # Возвращаем partial index, убираем обычный
    if _index_exists(bind, "uq_word_progress_user_vocabulary"):
        op.drop_index("uq_word_progress_user_vocabulary", table_name="word_progress")

    op.alter_column("word_progress", "vocabulary_id", nullable=True)

    # vocabulary_sense_links: возвращаем user_id
    if not _column_exists(bind, "vocabulary_sense_links", "user_id"):
        op.add_column("vocabulary_sense_links", sa.Column("user_id", sa.Integer(), nullable=True))
        bind.execute(sa.text("""
            UPDATE vocabulary_sense_links vsl
            SET user_id = uv.user_id
            FROM user_vocabulary uv
            WHERE uv.id = vsl.vocabulary_item_id
        """))
        op.alter_column("vocabulary_sense_links", "user_id", nullable=False)
        if _constraint_exists(bind, "vocabulary_sense_links", "uq_vocab_sense_link_vocab"):
            op.drop_constraint("uq_vocab_sense_link_vocab", "vocabulary_sense_links", type_="unique")
        op.create_unique_constraint("uq_vocab_sense_link_user_vocab", "vocabulary_sense_links", ["user_id", "vocabulary_item_id"])

    # sense_relations: возвращаем user_id (значение восстановить невозможно точно — ставим 0)
    if not _column_exists(bind, "sense_relations", "user_id"):
        op.add_column("sense_relations", sa.Column("user_id", sa.Integer(), nullable=True))
        bind.execute(sa.text("UPDATE sense_relations SET user_id = 0"))
        op.alter_column("sense_relations", "user_id", nullable=False)
        if _constraint_exists(bind, "sense_relations", "uq_sense_relation_pair"):
            op.drop_constraint("uq_sense_relation_pair", "sense_relations", type_="unique")
        op.create_unique_constraint("uq_sense_relation_pair", "sense_relations", ["user_id", "left_sense_id", "right_sense_id"])

    # word_senses: возвращаем user_id, source_sentence, source_url
    if not _column_exists(bind, "word_senses", "user_id"):
        op.add_column("word_senses", sa.Column("user_id", sa.Integer(), nullable=True))
        bind.execute(sa.text("UPDATE word_senses SET user_id = 0"))
        op.alter_column("word_senses", "user_id", nullable=False)
        if _column_exists(bind, "word_senses", "source_sentence") is False:
            op.add_column("word_senses", sa.Column("source_sentence", sa.Text(), nullable=True))
        if _column_exists(bind, "word_senses", "source_url") is False:
            op.add_column("word_senses", sa.Column("source_url", sa.String(2000), nullable=True))
        if _constraint_exists(bind, "word_senses", "uq_word_sense_lemma_key"):
            op.drop_constraint("uq_word_sense_lemma_key", "word_senses", type_="unique")
        op.create_unique_constraint("uq_word_sense_user_lemma_key", "word_senses", ["user_id", "english_lemma", "semantic_key"])

    # topic_clusters: возвращаем user_id
    if not _column_exists(bind, "topic_clusters", "user_id"):
        op.add_column("topic_clusters", sa.Column("user_id", sa.Integer(), nullable=True))
        bind.execute(sa.text("UPDATE topic_clusters SET user_id = 0"))
        op.alter_column("topic_clusters", "user_id", nullable=False)
        if _constraint_exists(bind, "topic_clusters", "uq_topic_cluster_key"):
            op.drop_constraint("uq_topic_cluster_key", "topic_clusters", type_="unique")
        op.create_unique_constraint("uq_topic_cluster_user_key", "topic_clusters", ["user_id", "cluster_key"])

    # base_lexicon_entries: воссоздаём пустую таблицу
    op.create_table(
        "base_lexicon_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("english_lemma", sa.String(200), nullable=False),
        sa.Column("russian_translation", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("english_lemma", name="uq_base_lexicon_english_lemma"),
    )
