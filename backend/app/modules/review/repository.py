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
    """Низкоуровневые запросы и SRS-обновления для `word_progress`."""

    _SRS_STEPS_DAYS = [1, 3, 7, 14, 30, 60]

    def __init__(self, db: Session = Depends(get_db)) -> None:
        self._db = db

    def update_word_progress(
        self,
        user_id: int,
        word: str,
        is_correct: bool,
    ) -> WordProgressModel | None:
        normalized = _normalize_valid_word(word)
        if not normalized:
            return None

        row = self._db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.word == normalized,
            )
        )
        now = datetime.utcnow()

        if row is None:
            row = WordProgressModel(
                user_id=user_id,
                word=normalized,
                error_count=0,
                correct_streak=0,
                last_reviewed_at=now,
                next_review_at=now,
            )
            self._db.add(row)
            self._db.flush()

        row.last_reviewed_at = now
        if is_correct:
            row.correct_streak += 1
            step_idx = min(row.correct_streak - 1, len(self._SRS_STEPS_DAYS) - 1)
            row.next_review_at = now + timedelta(days=self._SRS_STEPS_DAYS[step_idx])
        else:
            row.error_count += 1
            row.correct_streak = 0
            row.next_review_at = now
        return row

    def ensure_word_progress(self, user_id: int, word: str) -> WordProgressModel | None:
        normalized = _normalize_valid_word(word)
        if not normalized:
            return None

        row = self._db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.word == normalized,
            )
        )
        if row is not None:
            return row

        now = datetime.utcnow()
        row = WordProgressModel(
            user_id=user_id,
            word=normalized,
            error_count=0,
            correct_streak=0,
            last_reviewed_at=now,
            next_review_at=now,
        )
        self._db.add(row)
        self._db.flush()
        return row

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
