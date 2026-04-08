from datetime import datetime, timedelta
from typing import Literal
import re

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.modules.learning.review.models import WordProgressModel


class ContextMemoryRepository:
    _SRS_STEPS_DAYS = [1, 3, 7, 14, 30, 60]
    _WORD_RE = re.compile(r"^[a-z][a-z'-]{0,48}$")

    @classmethod
    def _normalize_valid_word(cls, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().lower()
        if not normalized or not cls._WORD_RE.fullmatch(normalized):
            return None
        return normalized

    def update_word_progress(
        self,
        db: Session,
        user_id: int,
        word: str,
        is_correct: bool,
    ) -> WordProgressModel | None:
        normalized = self._normalize_valid_word(word)
        if not normalized:
            return None

        row = db.scalar(
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
            db.add(row)
            db.flush()

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

    def ensure_word_progress(
        self,
        db: Session,
        user_id: int,
        word: str,
    ) -> WordProgressModel | None:
        normalized = self._normalize_valid_word(word)
        if not normalized:
            return None

        row = db.scalar(
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
        db.add(row)
        db.flush()
        return row

    def get_word_progress(
        self,
        db: Session,
        user_id: int,
        word: str,
    ) -> WordProgressModel | None:
        normalized = self._normalize_valid_word(word)
        if not normalized:
            return None
        return db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.word == normalized,
            )
        )

    def get_word_progress_map(
        self,
        db: Session,
        user_id: int,
        words: list[str],
    ) -> dict[str, WordProgressModel]:
        normalized = [word for word in (self._normalize_valid_word(item) for item in words) if word]
        if not normalized:
            return {}

        stmt = select(WordProgressModel).where(
            WordProgressModel.user_id == user_id,
            WordProgressModel.word.in_(normalized),
        )
        rows = list(db.scalars(stmt))
        return {row.word: row for row in rows}

    def list_due_word_progress(
        self,
        db: Session,
        user_id: int,
        limit: int,
    ) -> list[WordProgressModel]:
        now = datetime.utcnow()
        stmt = (
            select(WordProgressModel)
            .where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.next_review_at <= now,
            )
            .order_by(WordProgressModel.next_review_at.asc(), WordProgressModel.error_count.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt))

    def count_due_word_progress(
        self,
        db: Session,
        user_id: int,
    ) -> int:
        now = datetime.utcnow()
        stmt = select(func.count(WordProgressModel.id)).where(
            WordProgressModel.user_id == user_id,
            WordProgressModel.next_review_at <= now,
        )
        return int(db.scalar(stmt) or 0)

    def list_upcoming_word_progress(
        self,
        db: Session,
        user_id: int,
        horizon: timedelta,
        limit: int,
    ) -> list[WordProgressModel]:
        now = datetime.utcnow()
        end = now + horizon
        stmt = (
            select(WordProgressModel)
            .where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.next_review_at > now,
                WordProgressModel.next_review_at <= end,
            )
            .order_by(WordProgressModel.next_review_at.asc(), WordProgressModel.error_count.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt))

    def list_word_progress(
        self,
        db: Session,
        user_id: int,
        limit: int,
        offset: int,
        q: str | None = None,
        sort_by: Literal["next_review_at", "error_count", "correct_streak"] = "next_review_at",
        sort_order: Literal["asc", "desc"] = "asc",
    ) -> list[WordProgressModel]:
        stmt = select(WordProgressModel).where(WordProgressModel.user_id == user_id)

        if q:
            search = q.strip().lower()
            if search:
                stmt = stmt.where(WordProgressModel.word.contains(search))

        if sort_by == "error_count":
            primary_col = WordProgressModel.error_count
        elif sort_by == "correct_streak":
            primary_col = WordProgressModel.correct_streak
        else:
            primary_col = WordProgressModel.next_review_at

        primary_order = asc(primary_col) if sort_order == "asc" else desc(primary_col)
        stmt = stmt.order_by(primary_order, WordProgressModel.next_review_at.asc()).offset(offset).limit(limit)
        return list(db.scalars(stmt))

    def delete_word_progress(
        self,
        db: Session,
        user_id: int,
        word: str,
    ) -> bool:
        normalized = self._normalize_valid_word(word)
        if not normalized:
            return False

        row = db.scalar(
            select(WordProgressModel).where(
                WordProgressModel.user_id == user_id,
                WordProgressModel.word == normalized,
            )
        )
        if row is None:
            return False

        db.delete(row)
        db.flush()
        return True


context_repository = ContextMemoryRepository()
