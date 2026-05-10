from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DictionaryEntryModel(Base):
    """Общая запись словаря: лемма + конкретный смысл (перевод + определение).

    Уникальность по (english_lemma, russian_translation) — один смысл одна запись.
    Данные разделяются между всеми пользователями.
    """

    __tablename__ = "dictionary_entries"
    __table_args__ = (
        UniqueConstraint("english_lemma", "russian_translation", name="uq_dictionary_entry_lemma_translation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    english_lemma: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    russian_translation: Mapped[str] = mapped_column(String(200), nullable=False)
    context_definition_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class UserVocabularyModel(Base):
    """Личный словарь пользователя.

    Слова: entry_id → dictionary_entries, phrase_en/phrase_ru = NULL.
    Фразы: entry_id = NULL, phrase_en и phrase_ru заполнены.
    """

    __tablename__ = "user_vocabulary"
    __table_args__ = (
        UniqueConstraint("user_id", "entry_id", name="uq_user_vocabulary_user_entry"),
        UniqueConstraint("user_id", "phrase_en", name="uq_user_vocabulary_user_phrase"),
        CheckConstraint(
            "(entry_id IS NOT NULL) OR (phrase_en IS NOT NULL)",
            name="ck_user_vocabulary_word_or_phrase",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    entry_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_entries.id"), nullable=True, index=True)
    phrase_en: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    phrase_ru: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    @property
    def is_phrase(self) -> bool:
        return self.entry_id is None


class BaseLexiconEntryModel(Base):
    """Базовый офлайн-словарь для быстрого перевода без сетевых запросов."""

    __tablename__ = "base_lexicon_entries"
    __table_args__ = (
        UniqueConstraint("english_lemma", name="uq_base_lexicon_english_lemma"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    english_lemma: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    russian_translation: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class VocabularyItemLegacyModel(Base):
    """Совместимость со старой схемой: единая таблица vocabulary_items."""

    __tablename__ = "vocabulary_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    english_lemma: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    russian_translation: Mapped[str] = mapped_column(String(200), nullable=False)
    context_definition_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


@dataclass(frozen=True)
class CaptureModel:
    """Нормализованные входные данные capture-сценария."""

    user_id: int
    selected_text: str
    source_url: str | None
    source_sentence: str | None
    force_new_vocabulary_item: bool
