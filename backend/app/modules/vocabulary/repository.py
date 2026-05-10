from __future__ import annotations

from datetime import datetime

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.modules.vocabulary.models import (
    BaseLexiconEntryModel,
    DictionaryEntryModel,
    UserVocabularyModel,
)


def _legacy_row_to_models(row) -> tuple[UserVocabularyModel, DictionaryEntryModel]:
    timestamp = row.added_at or datetime.utcnow()
    uv = UserVocabularyModel(
        id=row.id,
        user_id=row.user_id,
        entry_id=row.id,
        source_sentence=row.source_sentence,
        source_url=row.source_url,
        added_at=timestamp,
    )
    entry = DictionaryEntryModel(
        id=row.id,
        english_lemma=row.english_lemma,
        russian_translation=row.russian_translation,
        context_definition_ru=row.context_definition_ru,
        created_at=timestamp,
    )
    return uv, entry

# ---------------------------------------------------------------------------
# DictionaryEntry — общий словарь
# ---------------------------------------------------------------------------

def get_or_create_dictionary_entry(
    db: Session,
    *,
    english_lemma: str,
    russian_translation: str,
    context_definition_ru: str | None,
) -> tuple[DictionaryEntryModel, bool]:
    """Возвращает (entry, created). Если запись уже есть — возвращает её.

    Если определение отсутствует в существующей записи, дополняет его.
    """
    normalized_lemma = english_lemma.strip().lower()
    normalized_translation = russian_translation.strip()

    existing = db.scalar(
        select(DictionaryEntryModel).where(
            DictionaryEntryModel.english_lemma == normalized_lemma,
            DictionaryEntryModel.russian_translation == normalized_translation,
        )
    )
    if existing is not None:
        if context_definition_ru and not existing.context_definition_ru:
            existing.context_definition_ru = context_definition_ru
            db.flush()
        return existing, False

    entry = DictionaryEntryModel(
        english_lemma=normalized_lemma,
        russian_translation=normalized_translation,
        context_definition_ru=context_definition_ru,
    )
    db.add(entry)
    db.flush()
    db.refresh(entry)
    return entry, True


def find_shared_translation(
    db: Session,
    *,
    english_lemma: str,
) -> str | None:
    """Возвращает наиболее популярный перевод из общего словаря для данной леммы."""
    normalized = english_lemma.strip().lower()
    if not normalized:
        return None
    row = db.execute(
        select(
            DictionaryEntryModel.russian_translation,
            func.count(UserVocabularyModel.id).label("cnt"),
            func.min(DictionaryEntryModel.id).label("first_id"),
        )
        .outerjoin(UserVocabularyModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
        .where(DictionaryEntryModel.english_lemma == normalized)
        .group_by(DictionaryEntryModel.russian_translation)
        .order_by(func.count(UserVocabularyModel.id).desc(), func.min(DictionaryEntryModel.id).asc())
        .limit(1)
    ).first()
    return row[0] if row else None


def list_definition_candidates(
    db: Session,
    *,
    english_lemma: str,
    limit: int = 20,
) -> list[DictionaryEntryModel]:
    normalized = english_lemma.strip().lower()
    if not normalized:
        return []
    return list(db.scalars(
        select(DictionaryEntryModel)
        .where(
            DictionaryEntryModel.english_lemma == normalized,
            DictionaryEntryModel.context_definition_ru.is_not(None),
        )
        .order_by(DictionaryEntryModel.id.desc())
        .limit(limit)
    ))


# ---------------------------------------------------------------------------
# UserVocabulary — личный словарь
# ---------------------------------------------------------------------------

def get_user_vocabulary_item(
    db: Session,
    *,
    user_id: int,
    item_id: int,
) -> tuple[UserVocabularyModel, DictionaryEntryModel] | None:
    try:
        row = db.execute(
            select(UserVocabularyModel, DictionaryEntryModel)
            .join(DictionaryEntryModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(
                UserVocabularyModel.id == item_id,
                UserVocabularyModel.user_id == user_id,
            )
        ).first()
    except ProgrammingError:
        db.rollback()
        return None
    return (row[0], row[1]) if row else None


def add_to_user_vocabulary(
    db: Session,
    *,
    user_id: int,
    entry_id: int,
    source_sentence: str | None,
    source_url: str | None,
) -> tuple[UserVocabularyModel, bool]:
    """Возвращает (item, created). Если слово уже в словаре — возвращает существующее."""
    existing = db.scalar(
        select(UserVocabularyModel).where(
            UserVocabularyModel.user_id == user_id,
            UserVocabularyModel.entry_id == entry_id,
        )
    )
    if existing is not None:
        return existing, False

    item = UserVocabularyModel(
        user_id=user_id,
        entry_id=entry_id,
        source_sentence=source_sentence,
        source_url=source_url,
    )
    db.add(item)
    db.flush()
    db.refresh(item)
    return item, True


def list_user_vocabulary(
    db: Session,
    *,
    user_id: int,
) -> list[tuple[UserVocabularyModel, DictionaryEntryModel]]:
    try:
        rows = db.execute(
            select(UserVocabularyModel, DictionaryEntryModel)
            .join(DictionaryEntryModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(UserVocabularyModel.user_id == user_id)
            .order_by(UserVocabularyModel.added_at.desc())
        ).all()
        return [(uv, entry) for uv, entry in rows]
    except ProgrammingError:
        db.rollback()
        # Legacy schema fallback: only vocabulary_items table exists.
        rows = db.execute(
            text(
                """
                SELECT id, user_id, english_lemma, russian_translation,
                       context_definition_ru, source_sentence, source_url,
                       NULL::timestamp AS added_at
                FROM vocabulary_items
                WHERE user_id = :user_id
                ORDER BY id DESC
                """
            ),
            {"user_id": user_id},
        ).all()
        return [_legacy_row_to_models(row) for row in rows]


def update_user_vocabulary_item(
    db: Session,
    item: UserVocabularyModel,
    *,
    source_sentence: str | None,
    source_url: str | None,
) -> UserVocabularyModel:
    item.source_sentence = source_sentence
    item.source_url = source_url
    db.flush()
    return item


def delete_user_vocabulary_item(
    db: Session,
    item: UserVocabularyModel,
) -> None:
    db.delete(item)
    db.flush()


def get_latest_vocabulary_item_by_lemma(
    db: Session,
    *,
    user_id: int,
    english_lemma: str,
) -> tuple[UserVocabularyModel, DictionaryEntryModel] | None:
    normalized = english_lemma.strip().lower()
    if not normalized:
        return None
    try:
        row = db.execute(
            select(UserVocabularyModel, DictionaryEntryModel)
            .join(DictionaryEntryModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(
                UserVocabularyModel.user_id == user_id,
                DictionaryEntryModel.english_lemma == normalized,
            )
            .order_by(UserVocabularyModel.added_at.desc())
            .limit(1)
        ).first()
        return (row[0], row[1]) if row else None
    except ProgrammingError:
        db.rollback()
        row = db.execute(
            text(
                """
                SELECT id, user_id, english_lemma, russian_translation,
                       context_definition_ru, source_sentence, source_url,
                       NULL::timestamp AS added_at
                FROM vocabulary_items
                WHERE user_id = :user_id
                  AND english_lemma = :lemma
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id, "lemma": normalized},
        ).first()
        if row is None:
            return None
        return _legacy_row_to_models(row)


# ---------------------------------------------------------------------------
# Вспомогательные запросы для смежных модулей
# ---------------------------------------------------------------------------

def get_translation_map(
    db: Session,
    *,
    user_id: int,
    english_lemmas: list[str],
) -> dict[str, str]:
    normalized = [l.strip().lower() for l in english_lemmas if l and l.strip()]
    if not normalized:
        return {}
    try:
        rows = db.execute(
            select(DictionaryEntryModel.english_lemma, DictionaryEntryModel.russian_translation)
            .join(UserVocabularyModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(
                UserVocabularyModel.user_id == user_id,
                DictionaryEntryModel.english_lemma.in_(normalized),
            )
            .order_by(UserVocabularyModel.added_at.desc())
        ).all()
    except ProgrammingError:
        db.rollback()
        legacy_stmt = text(
            """
            SELECT english_lemma, russian_translation
            FROM vocabulary_items
            WHERE user_id = :user_id
              AND english_lemma IN :lemmas
            ORDER BY id DESC
            """
        ).bindparams(bindparam("lemmas", expanding=True))
        rows = db.execute(legacy_stmt, {"user_id": user_id, "lemmas": normalized}).all()
    result: dict[str, str] = {}
    for lemma, translation in rows:
        if lemma not in result:
            result[lemma] = translation
    return result


def get_definition_map(
    db: Session,
    *,
    user_id: int,
    english_lemmas: list[str],
) -> dict[str, str]:
    normalized = [l.strip().lower() for l in english_lemmas if l and l.strip()]
    if not normalized:
        return {}
    try:
        rows = db.execute(
            select(DictionaryEntryModel.english_lemma, DictionaryEntryModel.context_definition_ru)
            .join(UserVocabularyModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(
                UserVocabularyModel.user_id == user_id,
                DictionaryEntryModel.english_lemma.in_(normalized),
                DictionaryEntryModel.context_definition_ru.is_not(None),
            )
            .order_by(UserVocabularyModel.added_at.desc())
        ).all()
    except ProgrammingError:
        db.rollback()
        legacy_stmt = text(
            """
            SELECT english_lemma, context_definition_ru
            FROM vocabulary_items
            WHERE user_id = :user_id
              AND english_lemma IN :lemmas
              AND context_definition_ru IS NOT NULL
            ORDER BY id DESC
            """
        ).bindparams(bindparam("lemmas", expanding=True))
        rows = db.execute(legacy_stmt, {"user_id": user_id, "lemmas": normalized}).all()
    result: dict[str, str] = {}
    for lemma, definition in rows:
        if lemma not in result:
            result[lemma] = definition
    return result


def list_english_lemmas(
    db: Session,
    *,
    user_id: int,
) -> list[str]:
    try:
        rows = list(db.scalars(
            select(DictionaryEntryModel.english_lemma)
            .join(UserVocabularyModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(UserVocabularyModel.user_id == user_id)
            .order_by(UserVocabularyModel.added_at.desc())
        ))
    except ProgrammingError:
        db.rollback()
        rows = list(
            db.scalars(
                text(
                    """
                    SELECT english_lemma
                    FROM vocabulary_items
                    WHERE user_id = :user_id
                    ORDER BY id DESC
                    """
                ),
                {"user_id": user_id},
            )
        )
    seen: set[str] = set()
    result: list[str] = []
    for lemma in rows:
        if lemma not in seen:
            seen.add(lemma)
            result.append(lemma)
    return result


# ---------------------------------------------------------------------------
# BaseLexicon — офлайн словарь
# ---------------------------------------------------------------------------

def get_base_lexicon_entry(
    db: Session,
    *,
    english_lemma: str,
) -> BaseLexiconEntryModel | None:
    normalized = english_lemma.strip().lower()
    if not normalized:
        return None
    return db.scalar(
        select(BaseLexiconEntryModel).where(BaseLexiconEntryModel.english_lemma == normalized)
    )


def count_base_lexicon_entries(db: Session) -> int:
    return int(db.scalar(select(func.count(BaseLexiconEntryModel.id))) or 0)


def seed_default_base_lexicon_entries(
    db: Session,
    *,
    entries: list[tuple[str, str]],
) -> int:
    created = 0
    for english_lemma, russian_translation in entries:
        normalized = (english_lemma or "").strip().lower()
        translated = (russian_translation or "").strip()
        if not normalized or not translated:
            continue
        if get_base_lexicon_entry(db, english_lemma=normalized) is not None:
            continue
        db.add(BaseLexiconEntryModel(english_lemma=normalized, russian_translation=translated))
        created += 1
    if created:
        db.commit()
    return created


def upsert_base_lexicon_entries(
    db: Session,
    *,
    entries: list[tuple[str, str]],
) -> int:
    updated = 0
    for english_lemma, russian_translation in entries:
        normalized = (english_lemma or "").strip().lower()
        translated = (russian_translation or "").strip()
        if not normalized or not translated:
            continue
        existing = get_base_lexicon_entry(db, english_lemma=normalized)
        if existing is None:
            db.add(BaseLexiconEntryModel(english_lemma=normalized, russian_translation=translated))
            updated += 1
        elif existing.russian_translation != translated:
            existing.russian_translation = translated
            updated += 1
    if updated:
        db.commit()
    return updated
