from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import Depends
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.review.models import WordProgressModel


class ReviewRepository:
    """Низкоуровневые запросы и CRUD для `word_progress`."""

    def __init__(self, db: Session = Depends(get_db)) -> None:
        self._db = db

    def get_or_create_word_progress(
        self,
        user_id: int,
        vocabulary_id: int,
        *,
        now: datetime,
    ) -> WordProgressModel:
        """Возвращает существующую SRS-карточку или создаёт новую с дефолтными значениями SM-2."""
        row = self._db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.vocabulary_id == vocabulary_id,
            )
        )
        if row is not None:
            return row
        row = WordProgressModel(
            user_id=user_id,
            vocabulary_id=vocabulary_id,
            error_count=0,
            correct_streak=0,
            ease_factor=2.5,
            interval_days=1,
            last_reviewed_at=now,
            next_review_at=now,
        )
        self._db.add(row)
        self._db.flush()
        return row

    def save_word_progress(
        self,
        row: WordProgressModel,
        *,
        error_count: int,
        correct_streak: int,
        ease_factor: float,
        interval_days: int,
        last_reviewed_at: datetime,
        next_review_at: datetime,
    ) -> WordProgressModel:
        row.error_count = error_count
        row.correct_streak = correct_streak
        row.ease_factor = ease_factor
        row.interval_days = interval_days
        row.last_reviewed_at = last_reviewed_at
        row.next_review_at = next_review_at
        self._db.flush()
        return row

    def ensure_word_progress(
        self,
        user_id: int,
        vocabulary_id: int,
    ) -> WordProgressModel | None:
        return self.get_or_create_word_progress(
            user_id, vocabulary_id, now=datetime.utcnow()
        )

    def get_word_progress_by_vocabulary_id(
        self, user_id: int, vocabulary_id: int
    ) -> WordProgressModel | None:
        return self._db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.vocabulary_id == vocabulary_id,
            )
        )

    def get_progress_map_by_vocabulary_ids(
        self, user_id: int, vocabulary_ids: list[int]
    ) -> dict[int, WordProgressModel]:
        if not vocabulary_ids:
            return {}
        rows = list(self._db.scalars(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.vocabulary_id.in_(vocabulary_ids),
            )
        ))
        return {row.vocabulary_id: row for row in rows}

    def list_due_word_progress(self, user_id: int, limit: int) -> list[WordProgressModel]:
        now = datetime.utcnow()
        return list(self._db.scalars(
            select(WordProgressModel)
            .where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.next_review_at <= now,
            )
            .order_by(WordProgressModel.next_review_at.asc(), WordProgressModel.error_count.desc())
            .limit(limit)
        ))

    def count_due_word_progress(self, user_id: int) -> int:
        now = datetime.utcnow()
        return int(self._db.scalar(
            select(func.count(WordProgressModel.id)).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.next_review_at <= now,
            )
        ) or 0)

    def list_upcoming_word_progress(
        self,
        user_id: int,
        horizon: timedelta,
        limit: int,
    ) -> list[WordProgressModel]:
        now = datetime.utcnow()
        end = now + horizon
        return list(self._db.scalars(
            select(WordProgressModel)
            .where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.next_review_at > now,
                WordProgressModel.next_review_at <= end,
            )
            .order_by(WordProgressModel.next_review_at.asc(), WordProgressModel.error_count.desc())
            .limit(limit)
        ))

    def list_word_progress(
        self,
        user_id: int,
        limit: int,
        offset: int,
        q: str | None = None,
        sort_by: Literal["next_review_at", "error_count", "correct_streak"] = "next_review_at",
        sort_order: Literal["asc", "desc"] = "asc",
    ) -> list[WordProgressModel]:
        query = select(WordProgressModel).where(WordProgressModel.user_id == user_id)

        if sort_by == "error_count":
            primary_col = WordProgressModel.error_count
        elif sort_by == "correct_streak":
            primary_col = WordProgressModel.correct_streak
        else:
            primary_col = WordProgressModel.next_review_at

        primary_order = asc(primary_col) if sort_order == "asc" else desc(primary_col)
        query = query.order_by(primary_order, WordProgressModel.next_review_at.asc()).offset(offset).limit(limit)
        return list(self._db.scalars(query))

    def delete_word_progress_by_vocabulary_id(self, user_id: int, vocabulary_id: int) -> bool:
        row = self._db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.vocabulary_id == vocabulary_id,
            )
        )
        if row is None:
            return False
        self._db.delete(row)
        self._db.flush()
        return True
