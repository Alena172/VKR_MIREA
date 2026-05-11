from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal

from fastapi import Depends
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.review.models import WordProgressModel

_WORD_RE = re.compile(r"^[a-z][a-z'-]{0,48}$")


def _normalize_valid_word(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized if normalized and _WORD_RE.fullmatch(normalized) else None


class ReviewRepository:
    """Низкоуровневые запросы и CRUD для `word_progress`."""

    def __init__(self, db: Session = Depends(get_db)) -> None:
        self._db = db

    def get_or_create_word_progress(
        self,
        user_id: int,
        word: str,
        *,
        now: datetime,
    ) -> WordProgressModel:
        """Возвращает существующую запись или создаёт новую с дефолтными значениями SM-2."""
        row = self._db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.word == word,
            )
        )
        if row is not None:
            return row
        row = WordProgressModel(
            user_id=user_id,
            word=word,
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
        """Сохраняет вычисленное состояние SRS в БД."""
        row.error_count = error_count
        row.correct_streak = correct_streak
        row.ease_factor = ease_factor
        row.interval_days = interval_days
        row.last_reviewed_at = last_reviewed_at
        row.next_review_at = next_review_at
        self._db.flush()
        return row

    def update_word_progress(
        self,
        user_id: int,
        word: str,
        is_correct: bool,
    ) -> WordProgressModel | None:
        """Устаревший метод-делегат: вызывается только из SRSService."""
        raise NotImplementedError(
            "update_word_progress moved to SRSService. Call SRSService.apply_review() instead."
        )

    def ensure_word_progress(self, user_id: int, word: str) -> WordProgressModel | None:
        normalized = _normalize_valid_word(word)
        if not normalized:
            return None
        return self.get_or_create_word_progress(user_id, normalized, now=datetime.utcnow())

    def get_word_progress(self, user_id: int, word: str) -> WordProgressModel | None:
        normalized = _normalize_valid_word(word)
        if not normalized:
            return None
        return self._db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.word == normalized,
            )
        )

    def get_word_progress_map(self, user_id: int, words: list[str]) -> dict[str, WordProgressModel]:
        normalized = [w for w in (_normalize_valid_word(item) for item in words) if w]
        if not normalized:
            return {}
        rows = list(self._db.scalars(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.word.in_(normalized),
            )
        ))
        return {row.word: row for row in rows}

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

        if q:
            search = q.strip().lower()
            if search:
                query = query.where(WordProgressModel.word.contains(search))

        if sort_by == "error_count":
            primary_col = WordProgressModel.error_count
        elif sort_by == "correct_streak":
            primary_col = WordProgressModel.correct_streak
        else:
            primary_col = WordProgressModel.next_review_at

        primary_order = asc(primary_col) if sort_order == "asc" else desc(primary_col)
        query = query.order_by(primary_order, WordProgressModel.next_review_at.asc()).offset(offset).limit(limit)
        return list(self._db.scalars(query))

    def delete_word_progress(self, user_id: int, word: str) -> bool:
        normalized = _normalize_valid_word(word)
        if not normalized:
            return False

        row = self._db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.word == normalized,
            )
        )
        if row is None:
            return False

        self._db.delete(row)
        self._db.flush()
        return True
