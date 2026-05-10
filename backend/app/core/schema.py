from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.modules.vocabulary.models import DictionaryEntryModel, UserVocabularyModel


def _table_exists(conn, table_name: str) -> bool:
    return bool(conn.execute(text(f"SELECT to_regclass('public.{table_name}')")).scalar())


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    return bool(conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table_name AND column_name = :column_name"
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar())


def _ensure_identity_columns(conn) -> None:
    if _table_exists(conn, "users") and not _column_exists(conn, "users", "password_hash"):
        conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(512)"))


def _rename_legacy_mistake_events(conn) -> None:
    if _table_exists(conn, "sense_error_events") or not _table_exists(conn, "mistake_events"):
        return
    conn.execute(text("ALTER TABLE mistake_events RENAME TO sense_error_events"))


def _bootstrap_shared_dictionary(conn) -> None:
    DictionaryEntryModel.__table__.create(bind=conn, checkfirst=True)
    UserVocabularyModel.__table__.create(bind=conn, checkfirst=True)

    if not _table_exists(conn, "vocabulary_items"):
        return

    added_at_expr = "COALESCE(added_at, NOW())" if _column_exists(conn, "vocabulary_items", "added_at") else "NOW()"

    conn.execute(text("""
        INSERT INTO dictionary_entries (english_lemma, russian_translation, context_definition_ru, created_at)
        SELECT DISTINCT ON (english_lemma, russian_translation)
               english_lemma,
               russian_translation,
               context_definition_ru,
               """ + added_at_expr + """
        FROM vocabulary_items
        WHERE context_definition_ru IS NOT NULL
        ORDER BY english_lemma, russian_translation, id DESC
        ON CONFLICT (english_lemma, russian_translation) DO NOTHING
    """))
    conn.execute(text("""
        INSERT INTO dictionary_entries (english_lemma, russian_translation, context_definition_ru, created_at)
        SELECT DISTINCT ON (english_lemma, russian_translation)
               english_lemma,
               russian_translation,
               NULL,
               """ + added_at_expr + """
        FROM vocabulary_items
        ORDER BY english_lemma, russian_translation, id DESC
        ON CONFLICT (english_lemma, russian_translation) DO NOTHING
    """))
    conn.execute(text("""
        INSERT INTO user_vocabulary (user_id, entry_id, source_sentence, source_url, added_at)
        SELECT DISTINCT ON (vi.user_id, de.id)
               vi.user_id,
               de.id,
               vi.source_sentence,
               vi.source_url,
               """ + added_at_expr.replace("added_at", "vi.added_at") + """
        FROM vocabulary_items vi
        JOIN dictionary_entries de
          ON de.english_lemma = vi.english_lemma
         AND de.russian_translation = vi.russian_translation
        ORDER BY vi.user_id, de.id, vi.id DESC
        ON CONFLICT (user_id, entry_id) DO NOTHING
    """))


def ensure_database_schema_ready(*, engine: Engine, database_url: str) -> None:
    """Гарантирует, что локальный PostgreSQL не отстал от обязательной схемы."""

    if engine.dialect.name != "postgresql":
        return

    needs_upgrade = False

    with engine.begin() as conn:
        dictionary_entries_exists = _table_exists(conn, "dictionary_entries")
        user_vocabulary_exists = _table_exists(conn, "user_vocabulary")
        sense_error_events_exists = _table_exists(conn, "sense_error_events")
        alembic_version_exists = _table_exists(conn, "alembic_version")

        current_version = None
        if alembic_version_exists:
            current_version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()

        shared_dictionary_ready = bool(dictionary_entries_exists and user_vocabulary_exists)
        if shared_dictionary_ready and sense_error_events_exists:
            return

        # Если 0013 была проставлена вручную, но таблицы не появились,
        # откатываем stamp и даем Alembic повторно выполнить migration body.
        if current_version == "0013_shared_dictionary":
            conn.execute(
                text(
                    "UPDATE alembic_version "
                    "SET version_num = '0012_rename_mistake_events_to_sense_error_events'"
                )
            )

        needs_upgrade = True

    if needs_upgrade:
        alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        alembic_cfg.set_main_option(
            "script_location",
            str(Path(__file__).resolve().parents[2] / "alembic"),
        )
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        if alembic_cfg.config_ini_section:
            alembic_cfg.set_section_option(alembic_cfg.config_ini_section, "sqlalchemy.url", database_url)
        command.upgrade(alembic_cfg, "head")

    with engine.begin() as conn:
        _ensure_identity_columns(conn)
        _rename_legacy_mistake_events(conn)
        if not (_table_exists(conn, "dictionary_entries") and _table_exists(conn, "user_vocabulary")):
            _bootstrap_shared_dictionary(conn)
