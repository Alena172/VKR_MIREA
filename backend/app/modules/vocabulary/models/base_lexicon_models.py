from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BaseLexiconEntryModel(Base):
    __tablename__ = "base_lexicon_entries"
    __table_args__ = (
        UniqueConstraint("english_lemma", name="uq_base_lexicon_english_lemma"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    english_lemma: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    russian_translation: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
