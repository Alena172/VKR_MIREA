from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WordProgressModel(Base):
    """Состояние SRS для одной записи личного словаря пользователя.

    Ключ: vocabulary_id — одна карточка = один смысл слова.
    Пользователь определяется через user_vocabulary.user_id.
    """

    __tablename__ = "word_progress"
    __table_args__ = (
        Index("uq_word_progress_vocabulary", "vocabulary_id", unique=True),
        Index("ix_word_progress_next_review_at", "next_review_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vocabulary_id: Mapped[int] = mapped_column(
        ForeignKey("user_vocabulary.id", ondelete="CASCADE"), nullable=False, index=True
    )
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


ReviewStatus = Literal["due", "upcoming", "mastered", "troubled"]
ReviewStatusFilter = Literal["all", "due", "upcoming", "mastered", "troubled"]


@dataclass(frozen=True)
class ReviewStatusSnapshot:
    status: ReviewStatus
    priority: int
    is_due: bool
    is_mastered: bool
    is_troubled: bool


_TROUBLED_EASE_THRESHOLD = 1.5
_MASTERED_EASE_THRESHOLD = 2.8


def build_review_status(
    *,
    error_count: int,
    correct_streak: int,
    next_review_at: datetime,
    ease_factor: float = 2.5,
    min_streak: int = 3,
    now: datetime | None = None,
) -> ReviewStatusSnapshot:
    current_time = now or datetime.utcnow()
    is_due = next_review_at <= current_time
    is_troubled = ease_factor <= _TROUBLED_EASE_THRESHOLD
    is_mastered = correct_streak >= min_streak and ease_factor >= _MASTERED_EASE_THRESHOLD

    if is_troubled and not is_mastered:
        return ReviewStatusSnapshot(status="troubled", priority=5, is_due=is_due, is_mastered=False, is_troubled=True)
    if is_due:
        return ReviewStatusSnapshot(status="due", priority=4, is_due=True, is_mastered=is_mastered, is_troubled=False)
    if is_mastered:
        return ReviewStatusSnapshot(status="mastered", priority=1, is_due=False, is_mastered=True, is_troubled=False)
    return ReviewStatusSnapshot(status="upcoming", priority=3, is_due=False, is_mastered=False, is_troubled=False)


def matches_review_status_filter(
    *,
    status_filter: ReviewStatusFilter,
    error_count: int,
    correct_streak: int,
    next_review_at: datetime,
    ease_factor: float = 2.5,
    min_streak: int = 3,
    now: datetime | None = None,
) -> bool:
    if status_filter == "all":
        return True
    snapshot = build_review_status(
        error_count=error_count,
        correct_streak=correct_streak,
        next_review_at=next_review_at,
        ease_factor=ease_factor,
        min_streak=min_streak,
        now=now,
    )
    return snapshot.status == status_filter
