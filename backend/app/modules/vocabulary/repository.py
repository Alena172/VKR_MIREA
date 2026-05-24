"""Репозиторий общего и пользовательского словаря."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy import bindparam, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.vocabulary.models import (
    DictionaryEntryModel,
    UserVocabularyModel,
)


class VocabularyRepository:
    """Содержит SQLAlchemy-запросы vocabulary-модуля и соседних сценариев."""

    def __init__(self, db: Session = Depends(get_db)) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # DictionaryEntry — таблица общего словаря
    # ------------------------------------------------------------------

    def get_or_create_dictionary_entry(
        self,
        *,
        english_lemma: str,
        russian_translation: str,
        context_definition_ru: str | None,
        topic_cluster_key: str | None = None,
    ) -> tuple[DictionaryEntryModel, bool]:
        """Находит или создаёт запись в общем словаре по лемме и переводу."""
        normalized_lemma = english_lemma.strip().lower()
        normalized_translation = russian_translation.strip()

        existing = self._db.scalar(
            select(DictionaryEntryModel).where(
                DictionaryEntryModel.english_lemma == normalized_lemma,
                DictionaryEntryModel.russian_translation == normalized_translation,
            )
        )
        if existing is not None:
            updated = False
            if context_definition_ru and not existing.context_definition_ru:
                existing.context_definition_ru = context_definition_ru
                updated = True
            if topic_cluster_key and not existing.topic_cluster_key:
                existing.topic_cluster_key = topic_cluster_key
                updated = True
            if updated:
                self._db.flush()
            return existing, False

        entry = DictionaryEntryModel(
            english_lemma=normalized_lemma,
            russian_translation=normalized_translation,
            context_definition_ru=context_definition_ru,
            topic_cluster_key=topic_cluster_key,
        )
        self._db.add(entry)
        self._db.flush()
        self._db.refresh(entry)
        return entry, True

    def count_shared_translations(self, *, english_lemma: str) -> int:
        """Считает, сколько переводов уже есть у данной леммы в общем словаре."""
        normalized = english_lemma.strip().lower()
        if not normalized:
            return 0
        return self._db.scalar(
            select(func.count(DictionaryEntryModel.id))
            .where(DictionaryEntryModel.english_lemma == normalized)
        ) or 0

    def find_shared_translation(self, *, english_lemma: str) -> str | None:
        """Возвращает самый распространённый перевод леммы среди пользовательских словарей."""
        normalized = english_lemma.strip().lower()
        if not normalized:
            return None
        row = self._db.execute(
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
        self,
        *,
        english_lemma: str,
        limit: int = 20,
    ) -> list[DictionaryEntryModel]:
        """Возвращает кандидаты со смысловыми определениями для AI-дизамбигуации."""
        normalized = english_lemma.strip().lower()
        if not normalized:
            return []
        return list(self._db.scalars(
            select(DictionaryEntryModel)
            .where(
                DictionaryEntryModel.english_lemma == normalized,
                DictionaryEntryModel.context_definition_ru.is_not(None),
            )
            .order_by(DictionaryEntryModel.id.desc())
            .limit(limit)
        ))

    # ------------------------------------------------------------------
    # UserVocabulary — таблица личного словаря
    # ------------------------------------------------------------------

    def get_user_vocabulary_item(
        self,
        *,
        user_id: int,
        item_id: int,
    ) -> tuple[UserVocabularyModel, DictionaryEntryModel] | None:
        """Возвращает пользовательский элемент словаря вместе с записью общего словаря."""
        row = self._db.execute(
            select(UserVocabularyModel, DictionaryEntryModel)
            .join(DictionaryEntryModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(
                UserVocabularyModel.id == item_id,
                UserVocabularyModel.user_id == user_id,
            )
        ).first()
        return (row[0], row[1]) if row else None

    def add_to_user_vocabulary(
        self,
        *,
        user_id: int,
        entry_id: int,
        source_sentence: str | None,
        source_url: str | None,
    ) -> tuple[UserVocabularyModel, bool]:
        """Добавляет слово в личный словарь, если такой пары user+entry ещё нет."""
        existing = self._db.scalar(
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
        self._db.add(item)
        self._db.flush()
        self._db.refresh(item)
        return item, True

    def add_phrase_to_user_vocabulary(
        self,
        *,
        user_id: int,
        phrase_en: str,
        phrase_ru: str,
        source_sentence: str | None,
        source_url: str | None,
    ) -> tuple[UserVocabularyModel, bool]:
        """Добавляет фразу в словарь пользователя без привязки к общему словарю лемм."""
        normalized = phrase_en.strip().lower()
        existing = self._db.scalar(
            select(UserVocabularyModel).where(
                UserVocabularyModel.user_id == user_id,
                UserVocabularyModel.phrase_en == normalized,
            )
        )
        if existing is not None:
            return existing, False

        item = UserVocabularyModel(
            user_id=user_id,
            entry_id=None,
            phrase_en=normalized,
            phrase_ru=phrase_ru.strip(),
            source_sentence=source_sentence,
            source_url=source_url,
        )
        self._db.add(item)
        self._db.flush()
        self._db.refresh(item)
        return item, True

    def count_user_vocabulary(self, *, user_id: int) -> int:
        """Считает все слова и фразы в словаре пользователя."""
        return int(self._db.scalar(
            select(func.count(UserVocabularyModel.id))
            .where(UserVocabularyModel.user_id == user_id)
        ) or 0)

    def list_user_vocabulary(self, *, user_id: int) -> list[tuple[UserVocabularyModel, DictionaryEntryModel | None]]:
        """Возвращает словарь пользователя в общем хронологическом порядке добавления."""
        word_rows = self._db.execute(
            select(UserVocabularyModel, DictionaryEntryModel)
            .join(DictionaryEntryModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(UserVocabularyModel.user_id == user_id)
            .order_by(UserVocabularyModel.added_at.desc())
        ).all()
        phrase_rows = list(self._db.scalars(
            select(UserVocabularyModel)
            .where(
                UserVocabularyModel.user_id == user_id,
                UserVocabularyModel.entry_id.is_(None),
            )
            .order_by(UserVocabularyModel.added_at.desc())
        ))
        result: list[tuple[UserVocabularyModel, DictionaryEntryModel | None]] = [
            (uv, entry) for uv, entry in word_rows
        ]
        result.extend((uv, None) for uv in phrase_rows)
        result.sort(key=lambda row: row[0].added_at, reverse=True)
        return result

    def update_user_vocabulary_item(
        self,
        item: UserVocabularyModel,
        *,
        source_sentence: str | None,
        source_url: str | None,
    ) -> UserVocabularyModel:
        """Обновляет контекстные пользовательские поля словарного элемента."""
        item.source_sentence = source_sentence
        item.source_url = source_url
        self._db.flush()
        return item

    def delete_user_vocabulary_item(self, item: UserVocabularyModel) -> None:
        """Удаляет элемент из личного словаря пользователя."""
        self._db.delete(item)
        self._db.flush()

    def get_latest_vocabulary_item_by_lemma(
        self,
        *,
        user_id: int,
        english_lemma: str,
    ) -> tuple[UserVocabularyModel, DictionaryEntryModel] | None:
        """Возвращает последнюю запись пользователя по указанной лемме."""
        normalized = english_lemma.strip().lower()
        if not normalized:
            return None
        row = self._db.execute(
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

    # ------------------------------------------------------------------
    # Вспомогательные запросы для смежных модулей
    # ------------------------------------------------------------------

    def get_translation_map(self, *, user_id: int, english_lemmas: list[str]) -> dict[str, str]:
        """Строит карту `lemma -> translation` для подмножества слов пользователя."""
        normalized = [l.strip().lower() for l in english_lemmas if l and l.strip()]
        if not normalized:
            return {}
        rows = self._db.execute(
            select(DictionaryEntryModel.english_lemma, DictionaryEntryModel.russian_translation)
            .join(UserVocabularyModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(
                UserVocabularyModel.user_id == user_id,
                DictionaryEntryModel.english_lemma.in_(normalized),
            )
            .order_by(UserVocabularyModel.added_at.desc())
        ).all()
        result: dict[str, str] = {}
        for lemma, translation in rows:
            if lemma not in result:
                result[lemma] = translation
        return result

    def get_definition_map(self, *, user_id: int, english_lemmas: list[str]) -> dict[str, str]:
        """Строит карту `lemma -> context_definition_ru` для слов пользователя."""
        normalized = [l.strip().lower() for l in english_lemmas if l and l.strip()]
        if not normalized:
            return {}
        rows = self._db.execute(
            select(DictionaryEntryModel.english_lemma, DictionaryEntryModel.context_definition_ru)
            .join(UserVocabularyModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(
                UserVocabularyModel.user_id == user_id,
                DictionaryEntryModel.english_lemma.in_(normalized),
                DictionaryEntryModel.context_definition_ru.is_not(None),
            )
            .order_by(UserVocabularyModel.added_at.desc())
        ).all()
        result: dict[str, str] = {}
        for lemma, definition in rows:
            if lemma not in result:
                result[lemma] = definition
        return result

    def list_senses_for_lemma(self, *, english_lemma: str) -> list[DictionaryEntryModel]:
        """Возвращает все сохранённые смыслы леммы из общего словаря."""
        normalized = english_lemma.strip().lower()
        return list(self._db.scalars(
            select(DictionaryEntryModel)
            .where(DictionaryEntryModel.english_lemma == normalized)
            .order_by(DictionaryEntryModel.id.asc())
        ))

    def find_user_vocabulary_by_entry(
        self,
        *,
        user_id: int,
        entry_id: int,
    ) -> UserVocabularyModel | None:
        """Проверяет, есть ли у пользователя элемент, указывающий на конкретный `entry_id`."""
        return self._db.scalar(
            select(UserVocabularyModel).where(
                UserVocabularyModel.user_id == user_id,
                UserVocabularyModel.entry_id == entry_id,
            )
        )

    def change_user_vocabulary_entry(
        self,
        item: UserVocabularyModel,
        *,
        new_entry_id: int,
    ) -> UserVocabularyModel:
        """Переключает пользовательский элемент на другую запись общего словаря."""
        item.entry_id = new_entry_id
        self._db.flush()
        return item

    def list_english_lemmas(self, *, user_id: int) -> list[str]:
        """Возвращает уникальные леммы пользователя в порядке недавнего добавления."""
        rows = list(self._db.scalars(
            select(DictionaryEntryModel.english_lemma)
            .join(UserVocabularyModel, UserVocabularyModel.entry_id == DictionaryEntryModel.id)
            .where(UserVocabularyModel.user_id == user_id)
            .order_by(UserVocabularyModel.added_at.desc())
        ))
        seen: set[str] = set()
        result: list[str] = []
        for lemma in rows:
            if lemma not in seen:
                seen.add(lemma)
                result.append(lemma)
        return result
