from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class VocabularyItemModel(Base):
    __tablename__ = "vocabulary_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    english_lemma: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    russian_translation: Mapped[str] = mapped_column(String(200), nullable=False)
    context_definition_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_definition_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_definition_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    definition_reused_from_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
