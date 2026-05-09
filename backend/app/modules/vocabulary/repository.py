from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.vocabulary.models import BaseLexiconEntryModel, VocabularyItemModel
from app.modules.vocabulary.schemas import VocabularyItemCreate


def list_vocabulary_items(db: Session, user_id: int | None) -> list[VocabularyItemModel]:
    query = select(VocabularyItemModel)
    if user_id is not None:
        query = query.where(VocabularyItemModel.user_id == user_id)
    query = query.order_by(VocabularyItemModel.id.desc())
    return list(db.scalars(query))


def create_vocabulary_item(
    db: Session,
    payload: VocabularyItemCreate,
    *,
    auto_commit: bool = True,
) -> VocabularyItemModel:
    item = VocabularyItemModel(**payload.model_dump())
    db.add(item)
    if auto_commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return item


def list_definition_candidates(
    db: Session,
    *,
    user_id: int,
    english_lemma: str,
    limit: int = 20,
) -> list[VocabularyItemModel]:
    normalized = english_lemma.strip().lower()
    if not normalized:
        return []
    query = (
        select(VocabularyItemModel)
        .where(
            VocabularyItemModel.user_id == user_id,
            VocabularyItemModel.english_lemma == normalized,
            VocabularyItemModel.context_definition_ru.is_not(None),
        )
        .order_by(VocabularyItemModel.id.desc())
        .limit(limit)
    )
    return list(db.scalars(query))


def get_vocabulary_item_for_user(db: Session, item_id: int, user_id: int) -> VocabularyItemModel | None:
    query = select(VocabularyItemModel).where(
        VocabularyItemModel.id == item_id,
        VocabularyItemModel.user_id == user_id,
    )
    return db.scalar(query)


def update_vocabulary_item(
    db: Session,
    item: VocabularyItemModel,
    *,
    english_lemma: str,
    russian_translation: str,
    source_sentence: str | None,
    source_url: str | None,
    auto_commit: bool = True,
) -> VocabularyItemModel:
    item.english_lemma = english_lemma.strip().lower()
    item.russian_translation = russian_translation.strip()
    item.source_sentence = source_sentence.strip() if source_sentence else None
    item.source_url = source_url.strip() if source_url else None
    db.add(item)
    if auto_commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return item


def delete_vocabulary_item(db: Session, item: VocabularyItemModel, *, auto_commit: bool = True) -> None:
    db.delete(item)
    if auto_commit:
        db.commit()
    else:
        db.flush()


def get_translation_map(
    db: Session,
    user_id: int,
    english_lemmas: list[str],
) -> dict[str, str]:
    normalized = [lemma.strip().lower() for lemma in english_lemmas if lemma and lemma.strip()]
    if not normalized:
        return {}

    query = (
        select(VocabularyItemModel)
        .where(
            VocabularyItemModel.user_id == user_id,
            VocabularyItemModel.english_lemma.in_(normalized),
        )
        .order_by(VocabularyItemModel.id.desc())
    )
    rows = list(db.scalars(query))

    result: dict[str, str] = {}
    for row in rows:
        key = row.english_lemma.strip().lower()
        if key not in result:
            result[key] = row.russian_translation
    return result


def get_definition_map(
    db: Session,
    user_id: int,
    english_lemmas: list[str],
) -> dict[str, str]:
    normalized = [lemma.strip().lower() for lemma in english_lemmas if lemma and lemma.strip()]
    if not normalized:
        return {}

    query = (
        select(VocabularyItemModel)
        .where(
            VocabularyItemModel.user_id == user_id,
            VocabularyItemModel.english_lemma.in_(normalized),
        )
        .order_by(VocabularyItemModel.id.desc())
    )
    rows = list(db.scalars(query))

    result: dict[str, str] = {}
    for row in rows:
        key = row.english_lemma.strip().lower()
        if key not in result and row.context_definition_ru:
            result[key] = row.context_definition_ru
    return result


def get_latest_vocabulary_item_by_lemma(
    db: Session,
    user_id: int,
    english_lemma: str,
) -> VocabularyItemModel | None:
    normalized = english_lemma.strip().lower()
    if not normalized:
        return None
    query = (
        select(VocabularyItemModel)
        .where(
            VocabularyItemModel.user_id == user_id,
            VocabularyItemModel.english_lemma == normalized,
        )
        .order_by(VocabularyItemModel.id.desc())
        .limit(1)
    )
    return db.scalar(query)


def list_english_lemmas(db: Session, user_id: int) -> list[str]:
    query = (
        select(VocabularyItemModel.english_lemma)
        .where(VocabularyItemModel.user_id == user_id)
        .order_by(VocabularyItemModel.id.desc())
    )
    rows = list(db.scalars(query))
    result: list[str] = []
    seen: set[str] = set()
    for lemma in rows:
        normalized = (lemma or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def get_base_lexicon_entry(
    db: Session,
    *,
    english_lemma: str,
) -> BaseLexiconEntryModel | None:
    normalized = english_lemma.strip().lower()
    if not normalized:
        return None
    return db.scalar(
        select(BaseLexiconEntryModel).where(
            BaseLexiconEntryModel.english_lemma == normalized,
        )
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
        db.add(
            BaseLexiconEntryModel(
                english_lemma=normalized,
                russian_translation=translated,
            )
        )
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
            db.add(
                BaseLexiconEntryModel(
                    english_lemma=normalized,
                    russian_translation=translated,
                )
            )
            updated += 1
            continue
        if existing.russian_translation != translated:
            existing.russian_translation = translated
            db.add(existing)
            updated += 1
    if updated:
        db.commit()
    return updated
