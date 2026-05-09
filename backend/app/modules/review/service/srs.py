from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.identity.service import get_user_by_id
from app.modules.review.models import (
    WordProgressModel,
    build_review_status,
    matches_review_status_filter,
)
from app.modules.review.repository import _normalize_valid_word, review_repository
from app.modules.review.schemas import (
    ReviewQueueBulkSubmitRequest,
    ReviewQueueSubmitRequest,
    ReviewSessionStartRequest,
)
from app.modules.review.service.scoring import recommendation_scoring_service
from app.modules.training.repository import get_progress_snapshot
from app.modules.vocabulary.service.items import (
    get_definition_map_for_user,
    get_translation_map_for_user,
    list_user_items,
)


@dataclass(frozen=True)
class WordProgressUpdate:
    word: str
    is_correct: bool


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        key = v.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


class SRSService:
    """Application-сервис SRS, очереди повторения и прогресса слов."""

    def _ensure_user_access(self, *, db: Session, user_id: int, current_user_id: int):
        if user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        if get_user_by_id(db, user_id) is None:
            raise HTTPException(status_code=404, detail="User not found")

    def get_review_queue(self, *, db: Session, user_id: int, current_user_id: int, limit: int) -> dict:
        self._ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        due_progress = review_repository.list_due_word_progress(db, user_id=user_id, limit=limit * 5)
        total_due = review_repository.count_due_word_progress(db, user_id=user_id)
        items = self._build_review_queue_items(db=db, user_id=user_id, rows=due_progress)[:limit]
        return {"user_id": user_id, "total_due": total_due, "items": items}

    def submit_review_queue_item(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        payload: ReviewQueueSubmitRequest,
    ) -> WordProgressModel:
        self._ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        normalized = _normalize_valid_word(payload.word)
        if normalized is None:
            raise HTTPException(status_code=400, detail="Word must be a single english token")
        progress = review_repository.update_word_progress(db, user_id=user_id, word=normalized, is_correct=payload.is_correct)
        db.refresh(progress)
        return progress

    def submit_review_queue_bulk(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        payload: ReviewQueueBulkSubmitRequest,
    ) -> dict:
        self._ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        if not payload.items:
            return {"user_id": user_id, "updated": []}
        updated_rows: list[WordProgressModel] = []
        for item in payload.items:
            normalized = _normalize_valid_word(item.word)
            if normalized is None:
                continue
            progress = review_repository.update_word_progress(db, user_id=user_id, word=normalized, is_correct=item.is_correct)
            if progress is not None:
                updated_rows.append(progress)
        return {"user_id": user_id, "updated": updated_rows}

    def start_review_session(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        payload: ReviewSessionStartRequest,
    ) -> dict:
        self._ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        if payload.mode == "srs":
            return self._build_srs_review_session(db=db, user_id=user_id, size=payload.size)
        return self._build_random_review_session(db=db, user_id=user_id, size=payload.size)

    def _build_srs_review_session(self, *, db: Session, user_id: int, size: int) -> dict:
        due_rows = review_repository.list_due_word_progress(db, user_id=user_id, limit=size * 5)
        words = _dedupe_keep_order([row.word for row in due_rows if _normalize_valid_word(row.word)])[:size]
        row_map = {row.word: row for row in due_rows}
        items = self._build_review_session_items(db=db, user_id=user_id, words=words, progress_map=row_map)
        return {"user_id": user_id, "mode": "srs", "total_items": len(items), "items": items}

    def _build_random_review_session(self, *, db: Session, user_id: int, size: int) -> dict:
        vocabulary_items = list_user_items(db=db, user_id=user_id)
        unique_words = _dedupe_keep_order(
            [item.english_lemma for item in vocabulary_items if _normalize_valid_word(item.english_lemma)]
        )
        if not unique_words:
            return {"user_id": user_id, "mode": "random", "total_items": 0, "items": []}
        random_words = secrets.SystemRandom().sample(unique_words, k=min(size, len(unique_words)))
        progress_map = review_repository.get_word_progress_map(db, user_id=user_id, words=random_words)
        items = self._build_review_session_items(db=db, user_id=user_id, words=random_words, progress_map=progress_map)
        return {"user_id": user_id, "mode": "random", "total_items": len(items), "items": items}

    def list_word_progress(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        limit: int,
        offset: int,
        status: Literal["all", "due", "upcoming", "mastered", "troubled"],
        q: str | None,
        sort_by: Literal["next_review_at", "error_count", "correct_streak"],
        sort_order: Literal["asc", "desc"],
        min_streak: int,
        min_errors: int,
    ) -> dict:
        self._ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        rows = review_repository.list_word_progress(
            db, user_id=user_id, limit=10000, offset=0, q=q, sort_by=sort_by, sort_order=sort_order,
        )
        if status != "all":
            rows = [
                row for row in rows
                if matches_review_status_filter(
                    status_filter=status,
                    error_count=row.error_count,
                    correct_streak=row.correct_streak,
                    next_review_at=row.next_review_at,
                    min_streak=min_streak,
                    min_errors=min_errors,
                )
            ]
        total = len(rows)
        page_rows = rows[offset:offset + limit]
        translation_map = get_translation_map_for_user(db, user_id=user_id, english_lemmas=[r.word for r in page_rows])
        items = [self._row_to_progress_dict(row, translation_map, user_id) for row in page_rows]
        return {"user_id": user_id, "total": total, "limit": limit, "offset": offset, "items": items}

    def get_word_progress(self, *, db: Session, user_id: int, current_user_id: int, word: str) -> WordProgressModel:
        self._ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        progress = review_repository.get_word_progress(db, user_id=user_id, word=word)
        if progress is None:
            raise HTTPException(status_code=404, detail="Word progress not found")
        return progress

    def delete_word_progress(self, *, db: Session, user_id: int, current_user_id: int, word: str) -> dict:
        self._ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        deleted = review_repository.delete_word_progress(db, user_id=user_id, word=word)
        return {"user_id": user_id, "word": word.strip().lower(), "progress_deleted": deleted}

    def get_review_plan(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        limit: int,
        horizon_hours: int,
    ) -> dict:
        self._ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        due_progress = review_repository.list_due_word_progress(db, user_id=user_id, limit=limit)
        upcoming_progress = review_repository.list_upcoming_word_progress(
            db, user_id=user_id, horizon=timedelta(hours=horizon_hours), limit=limit,
        )
        due_now = self._build_review_queue_items(db=db, user_id=user_id, rows=due_progress)
        upcoming = self._build_review_queue_items(db=db, user_id=user_id, rows=upcoming_progress)
        snapshot = recommendation_scoring_service.build_snapshot(db=db, user_id=user_id, limit=limit)
        return {
            "user_id": user_id,
            "due_count": len(due_now),
            "upcoming_count": len(upcoming),
            "due_now": due_now,
            "upcoming": upcoming,
            "recommended_words": snapshot.ranked_words(limit),
        }

    def get_review_summary(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        min_streak: int,
        min_errors: int,
    ) -> dict:
        self._ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        rows = review_repository.list_word_progress(db, user_id=user_id, limit=10000, offset=0, q=None)
        if not rows:
            return {"user_id": user_id, "total_tracked": 0, "due_now": 0, "mastered": 0, "troubled": 0}
        statuses = [
            build_review_status(
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                min_streak=min_streak,
                min_errors=min_errors,
            ).status
            for row in rows
        ]
        return {
            "user_id": user_id,
            "total_tracked": len(rows),
            "due_now": statuses.count("due"),
            "mastered": statuses.count("mastered"),
            "troubled": statuses.count("troubled"),
        }

    def get_progress_snapshot(self, *, db: Session, user_id: int | None, current_user_id: int) -> dict:
        if user_id is not None and user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        target = user_id or current_user_id
        total_sessions, avg_accuracy = get_progress_snapshot(db, user_id=target)
        return {"user_id": target, "total_sessions": total_sessions, "avg_accuracy": avg_accuracy}

    def ensure_word_progress_entry(self, *, db: Session, user_id: int, word: str) -> bool:
        return review_repository.ensure_word_progress(db, user_id=user_id, word=word) is not None

    def update_learning_progress(
        self,
        *,
        db: Session,
        user_id: int,
        updates: list[WordProgressUpdate],
    ) -> list[str]:
        updated_words: list[str] = []
        for update in updates:
            if update.word:
                progress = review_repository.update_word_progress(
                    db, user_id=user_id, word=update.word, is_correct=update.is_correct,
                )
                if progress is not None:
                    updated_words.append(progress.word)
        return _dedupe_keep_order(updated_words)

    def list_mastered_lemmas(self, *, db: Session, user_id: int, min_streak: int = 2, max_errors: int = 1) -> set[str]:
        rows = review_repository.list_word_progress(
            db, user_id=user_id, limit=10000, offset=0, q=None,
            sort_by="correct_streak", sort_order="desc",
        )
        return {
            row.word.strip().lower()
            for row in rows
            if row.word
            and row.error_count <= max_errors
            and build_review_status(
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                min_streak=min_streak,
                min_errors=max_errors + 1,
            ).status == "mastered"
        }

    def _build_review_queue_items(self, *, db: Session, user_id: int, rows: list[WordProgressModel]) -> list[dict]:
        words = [row.word for row in rows]
        translation_map = get_translation_map_for_user(db, user_id=user_id, english_lemmas=words)
        return [
            {
                "word": row.word,
                "russian_translation": translation_map.get(row.word),
                "next_review_at": row.next_review_at,
                "error_count": row.error_count,
                "correct_streak": row.correct_streak,
                "status": build_review_status(
                    error_count=row.error_count,
                    correct_streak=row.correct_streak,
                    next_review_at=row.next_review_at,
                ).status,
            }
            for row in rows
            if _normalize_valid_word(row.word) is not None
        ]

    def _build_review_session_items(
        self,
        *,
        db: Session,
        user_id: int,
        words: list[str],
        progress_map: dict[str, WordProgressModel],
    ) -> list[dict]:
        translation_map = get_translation_map_for_user(db, user_id=user_id, english_lemmas=words)
        definition_map = get_definition_map_for_user(db, user_id=user_id, english_lemmas=words)
        now = datetime.utcnow()
        items = []
        for word in words:
            p = progress_map.get(word)
            error_count = p.error_count if p else 0
            correct_streak = p.correct_streak if p else 0
            next_review_at = p.next_review_at if p else now
            items.append({
                "word": word,
                "russian_translation": translation_map.get(word),
                "context_definition": definition_map.get(word),
                "next_review_at": next_review_at,
                "error_count": error_count,
                "correct_streak": correct_streak,
                "status": build_review_status(
                    error_count=error_count,
                    correct_streak=correct_streak,
                    next_review_at=next_review_at,
                ).status,
            })
        return items

    def _row_to_progress_dict(self, row: WordProgressModel, translation_map: dict[str, str | None], user_id: int) -> dict:
        return {
            "user_id": user_id,
            "word": row.word,
            "russian_translation": translation_map.get(row.word),
            "error_count": row.error_count,
            "correct_streak": row.correct_streak,
            "next_review_at": row.next_review_at,
            "status": build_review_status(
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
            ).status,
        }


srs_service = SRSService()
