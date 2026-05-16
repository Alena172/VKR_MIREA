from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from fastapi import Depends, HTTPException

from app.modules.identity.service import IdentityService
from app.modules.review.models import (
    WordProgressModel,
    build_review_status,
    matches_review_status_filter,
)
from app.modules.review.repository import ReviewRepository
from app.modules.review.service.scoring import RecommendationScoringService

_SM2_EASE_DEFAULT = 2.5
_SM2_EASE_MIN = 1.3
_SM2_EASE_CORRECT_DELTA = 0.1
_SM2_EASE_WRONG_DELTA = 0.2
_SM2_INITIAL_INTERVAL = 1
_SM2_SECOND_INTERVAL = 3


def _sm2_next_interval(*, interval_days: int, ease_factor: float, correct_streak: int) -> int:
    if correct_streak == 1:
        return _SM2_INITIAL_INTERVAL
    if correct_streak == 2:
        return _SM2_SECOND_INTERVAL
    return max(1, round(interval_days * ease_factor))


if TYPE_CHECKING:
    from app.modules.training.service.submission import SubmissionService
    from app.modules.vocabulary.service.items import VocabularyService


@dataclass(frozen=True)
class WordProgressUpdate:
    vocabulary_id: int
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
    """Сервис уровня application для SRS, очереди повторения и прогресса слов."""

    def __init__(
        self,
        repo: ReviewRepository = Depends(),
        scoring_service: RecommendationScoringService = Depends(),
        identity_service: IdentityService = Depends(),
        vocabulary_service: Any = None,
    ) -> None:
        self._repo = repo
        self._scoring = scoring_service
        self._identity_service = identity_service
        self._vocabulary_service = vocabulary_service
        self._submission_service: SubmissionService | None = None

    def set_submission_service(self, submission_service: SubmissionService) -> None:
        self._submission_service = submission_service
        self._scoring.set_submission_service(submission_service)

    def _vocab(self) -> VocabularyService:
        if self._vocabulary_service is None:
            from app.modules.vocabulary.repository import VocabularyRepository
            from app.modules.vocabulary.service.items import VocabularyService
            self._vocabulary_service = VocabularyService(VocabularyRepository(self._repo._db))
        return self._vocabulary_service

    def _ensure_user_access(self, *, user_id: int, current_user_id: int):
        if user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        self._identity_service.get_user_or_404(user_id=user_id)

    def get_review_queue(self, *, user_id: int, current_user_id: int, limit: int) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        due_progress = self._repo.list_due_word_progress(user_id=user_id, limit=limit * 5)
        total_due = self._repo.count_due_word_progress(user_id=user_id)
        items = self._build_review_queue_items(user_id=user_id, rows=due_progress)[:limit]
        return {"user_id": user_id, "total_due": total_due, "items": items}

    def submit_review_queue_item(self, *, user_id: int, current_user_id: int, payload) -> WordProgressModel:
        from app.core.db import transaction
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        vocabulary_id = payload.vocabulary_id
        if vocabulary_id is None:
            word = getattr(payload, "word", None)
            if word:
                items = self._vocab().list_user_items(user_id=user_id)
                match = next((item for item in items if item.english_lemma.lower() == word.strip().lower()), None)
                if match:
                    vocabulary_id = match.id
        if vocabulary_id is None:
            raise HTTPException(status_code=400, detail="word not found in vocabulary or vocabulary_id is required")
        with transaction(self._repo._db):
            return self.apply_review(user_id=user_id, vocabulary_id=vocabulary_id, is_correct=payload.is_correct)

    def submit_review_queue_bulk(self, *, user_id: int, current_user_id: int, payload) -> dict:
        from app.core.db import transaction
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        if not payload.items:
            return {"user_id": user_id, "updated": []}
        vocab_items = self._vocab().list_user_items(user_id=user_id)
        word_to_id = {item.english_lemma.lower(): item.id for item in vocab_items}
        updated_rows: list[WordProgressModel] = []
        with transaction(self._repo._db):
            for item in payload.items:
                vid = getattr(item, "vocabulary_id", None)
                if vid is None:
                    word = getattr(item, "word", None)
                    if word:
                        vid = word_to_id.get(word.strip().lower())
                if vid is None:
                    continue
                progress = self.apply_review(user_id=user_id, vocabulary_id=vid, is_correct=item.is_correct)
                if progress is not None:
                    updated_rows.append(progress)
        return {"user_id": user_id, "updated": updated_rows}

    def start_review_session(self, *, user_id: int, current_user_id: int, payload) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        if payload.mode == "srs":
            return self._build_srs_review_session(user_id=user_id, size=payload.size)
        return self._build_random_review_session(user_id=user_id, size=payload.size)

    def _build_srs_review_session(self, *, user_id: int, size: int) -> dict:
        due_rows = self._repo.list_due_word_progress(user_id=user_id, limit=size * 5)
        due_rows = due_rows[:size]
        items = self._build_review_session_items_from_progress(user_id=user_id, rows=due_rows)
        return {"user_id": user_id, "mode": "srs", "total_items": len(items), "items": items}

    def _build_random_review_session(self, *, user_id: int, size: int) -> dict:
        vocabulary_items = self._vocab().list_user_items(user_id=user_id)
        valid_items = [item for item in vocabulary_items if item.english_lemma]
        if not valid_items:
            return {"user_id": user_id, "mode": "random", "total_items": 0, "items": []}
        sampled = secrets.SystemRandom().sample(valid_items, k=min(size, len(valid_items)))
        vocab_ids = [item.id for item in sampled]
        progress_map = self._repo.get_progress_map_by_vocabulary_ids(vocabulary_ids=vocab_ids)
        items = self._build_review_session_items_from_vocab(user_id=user_id, vocab_items=sampled, progress_map=progress_map)
        return {"user_id": user_id, "mode": "random", "total_items": len(items), "items": items}

    def list_word_progress(
        self,
        *,
        user_id: int,
        current_user_id: int,
        limit: int,
        offset: int,
        status: Literal["all", "due", "upcoming", "mastered", "troubled"],
        q: str | None,
        sort_by: Literal["next_review_at", "error_count", "correct_streak"],
        sort_order: Literal["asc", "desc"],
        min_streak: int,
        min_errors: int = 3,
    ) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        rows = self._repo.list_word_progress(user_id=user_id, limit=10000, offset=0, q=None, sort_by=sort_by, sort_order=sort_order)
        vocab_map = {item.id: item for item in self._vocab().list_user_items(user_id=user_id)}
        rows = [row for row in rows if row.vocabulary_id in vocab_map]
        if q:
            q_lower = q.strip().lower()
            rows = [
                row for row in rows
                if q_lower in vocab_map[row.vocabulary_id].english_lemma.lower()
            ]
        if status != "all":
            rows = [
                row for row in rows
                if matches_review_status_filter(
                    status_filter=status,
                    error_count=row.error_count,
                    correct_streak=row.correct_streak,
                    next_review_at=row.next_review_at,
                    ease_factor=row.ease_factor,
                    min_streak=min_streak,
                )
                and (status != "troubled" or row.error_count >= min_errors)
            ]
        total = len(rows)
        page_rows = rows[offset:offset + limit]
        items = [self._row_to_progress_dict(row, vocab_map, user_id) for row in page_rows]
        return {"user_id": user_id, "total": total, "limit": limit, "offset": offset, "items": items}

    def delete_word_progress(self, *, user_id: int, current_user_id: int, vocabulary_id: int | None = None, word: str | None = None) -> dict:
        from app.core.db import transaction
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        if vocabulary_id is None and word:
            items = self._vocab().list_user_items(user_id=user_id)
            match = next((item for item in items if item.english_lemma.lower() == word.strip().lower()), None)
            if match:
                vocabulary_id = match.id
        if vocabulary_id is None:
            return {"user_id": user_id, "vocabulary_id": None, "progress_deleted": False, "removed_from_difficult_words": False}
        with transaction(self._repo._db):
            deleted = self._repo.delete_word_progress_by_vocabulary_id(vocabulary_id=vocabulary_id)
        return {"user_id": user_id, "vocabulary_id": vocabulary_id, "progress_deleted": deleted, "removed_from_difficult_words": deleted}

    def get_review_plan(self, *, user_id: int, current_user_id: int, limit: int, horizon_hours: int) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        due_progress = self._repo.list_due_word_progress(user_id=user_id, limit=limit)
        upcoming_progress = self._repo.list_upcoming_word_progress(user_id=user_id, horizon=timedelta(hours=horizon_hours), limit=limit)
        due_now = self._build_review_queue_items(user_id=user_id, rows=due_progress)
        upcoming = self._build_review_queue_items(user_id=user_id, rows=upcoming_progress)
        snapshot = self._scoring.build_snapshot(user_id=user_id, limit=limit)
        return {
            "user_id": user_id,
            "due_count": len(due_now),
            "upcoming_count": len(upcoming),
            "due_now": due_now,
            "upcoming": upcoming,
            "recommended_words": snapshot.ranked_words(limit),
        }

    def get_review_summary(self, *, user_id: int, current_user_id: int, min_streak: int) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        rows = self._repo.list_word_progress(user_id=user_id, limit=10000, offset=0, q=None)
        if not rows:
            return {"user_id": user_id, "total_tracked": 0, "due_now": 0, "mastered": 0, "troubled": 0}
        statuses = [
            build_review_status(
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                ease_factor=row.ease_factor,
                min_streak=min_streak,
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

    def get_progress_snapshot(self, *, user_id: int | None, current_user_id: int) -> dict:
        if user_id is not None and user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        target = user_id or current_user_id
        total_sessions, avg_accuracy = (
            self._submission_service.get_progress_snapshot(user_id=target)
            if self._submission_service is not None
            else (0, 0.0)
        )
        return {"user_id": target, "total_sessions": total_sessions, "avg_accuracy": avg_accuracy}

    def apply_review(
        self,
        *,
        user_id: int,
        vocabulary_id: int,
        is_correct: bool,
    ) -> WordProgressModel | None:
        now = datetime.utcnow()
        row = self._repo.get_or_create_word_progress(vocabulary_id, now=now)

        if is_correct:
            new_streak = row.correct_streak + 1
            new_ease = row.ease_factor + _SM2_EASE_CORRECT_DELTA
            new_interval = _sm2_next_interval(interval_days=row.interval_days, ease_factor=new_ease, correct_streak=new_streak)
            return self._repo.save_word_progress(
                row,
                error_count=row.error_count,
                correct_streak=new_streak,
                ease_factor=new_ease,
                interval_days=new_interval,
                last_reviewed_at=now,
                next_review_at=now + timedelta(days=new_interval),
            )
        else:
            return self._repo.save_word_progress(
                row,
                error_count=row.error_count + 1,
                correct_streak=0,
                ease_factor=max(_SM2_EASE_MIN, row.ease_factor - _SM2_EASE_WRONG_DELTA),
                interval_days=_SM2_INITIAL_INTERVAL,
                last_reviewed_at=now,
                next_review_at=now,
            )

    def ensure_word_progress_entry(self, *, user_id: int, vocabulary_id: int) -> bool:
        return self._repo.ensure_word_progress(vocabulary_id=vocabulary_id) is not None

    def update_learning_progress(self, *, user_id: int, updates: list[WordProgressUpdate]) -> list[int]:
        updated_ids: list[int] = []
        for update in updates:
            progress = self.apply_review(user_id=user_id, vocabulary_id=update.vocabulary_id, is_correct=update.is_correct)
            if progress is not None:
                updated_ids.append(progress.vocabulary_id)
        return updated_ids

    def get_recommendations(self, *, user_id: int, current_user_id: int, limit: int) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        snapshot = self._scoring.build_snapshot(user_id=user_id, limit=limit)
        words = snapshot.ranked_words(limit)

        recent_error_words = []
        if self._submission_service is not None:
            for w in self._submission_service.list_recent_incorrect_words(user_id=user_id, limit=limit * 5, unique=True):
                if w and w not in recent_error_words:
                    recent_error_words.append(w)
                    if len(recent_error_words) >= limit:
                        break

        troubled_rows = [
            row for row in self._repo.list_word_progress(
                user_id=user_id, limit=limit * 3, offset=0, q=None,
                sort_by="error_count", sort_order="desc",
            )
            if row.error_count > 0
        ]
        # Берём english_lemma из user_vocabulary через vocab_map
        vocab_map = {item.id: item for item in self._vocab().list_user_items(user_id=user_id)}
        difficult_words = [
            vocab_map[row.vocabulary_id].english_lemma
            for row in troubled_rows
            if row.vocabulary_id in vocab_map
        ][:limit]

        all_words = list(dict.fromkeys(words + recent_error_words + difficult_words))[:limit * 2]
        scores = {w: snapshot.scores.get(w, 0.0) for w in all_words}

        return {
            "user_id": user_id,
            "words": words,
            "recent_error_words": recent_error_words,
            "difficult_words": difficult_words,
            "scores": scores,
            "next_review_at": {},
        }

    def get_user_context(self, *, user_id: int, current_user_id: int) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        troubled_rows = [
            row for row in self._repo.list_word_progress(
                user_id=user_id, limit=200, offset=0, q=None,
                sort_by="error_count", sort_order="desc",
            )
            if row.error_count > 0
        ]
        vocab_map = {item.id: item for item in self._vocab().list_user_items(user_id=user_id)}
        difficult_words = [
            vocab_map[row.vocabulary_id].english_lemma
            for row in troubled_rows
            if row.vocabulary_id in vocab_map
        ]
        user = self._identity_service.get_user_by_id(user_id)
        return {
            "user_id": user_id,
            "cefr_level": user.cefr_level if user else None,
            "goals": [],
            "difficult_words": difficult_words,
        }

    def list_mastered_lemmas(self, *, user_id: int, min_streak: int = 2, max_errors: int = 1) -> set[str]:
        rows = self._repo.list_word_progress(
            user_id=user_id, limit=10000, offset=0, q=None,
            sort_by="correct_streak", sort_order="desc",
        )
        vocab_map = {item.id: item for item in self._vocab().list_user_items(user_id=user_id)}
        return {
            vocab_map[row.vocabulary_id].english_lemma.strip().lower()
            for row in rows
            if row.vocabulary_id in vocab_map
            and row.error_count <= max_errors
            and build_review_status(
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                ease_factor=row.ease_factor,
                min_streak=min_streak,
            ).status == "mastered"
        }

    def _build_review_queue_items(self, *, user_id: int, rows: list[WordProgressModel]) -> list[dict]:
        vocab_map = {item.id: item for item in self._vocab().list_user_items(user_id=user_id)}
        result = []
        for row in rows:
            vocab_item = vocab_map.get(row.vocabulary_id)
            if vocab_item is None:
                continue
            result.append({
                "word": vocab_item.english_lemma,
                "russian_translation": vocab_item.russian_translation,
                "next_review_at": row.next_review_at,
                "error_count": row.error_count,
                "correct_streak": row.correct_streak,
                "status": build_review_status(
                    error_count=row.error_count,
                    correct_streak=row.correct_streak,
                    next_review_at=row.next_review_at,
                    ease_factor=row.ease_factor,
                ).status,
            })
        return result

    def _build_review_session_items_from_progress(self, *, user_id: int, rows: list[WordProgressModel]) -> list[dict]:
        vocab_map = {item.id: item for item in self._vocab().list_user_items(user_id=user_id)} if rows else {}
        items = []
        for row in rows:
            vocab_item = vocab_map.get(row.vocabulary_id)
            if vocab_item is None:
                continue
            items.append({
                "word": vocab_item.english_lemma,
                "vocabulary_id": row.vocabulary_id,
                "russian_translation": vocab_item.russian_translation,
                "context_definition": getattr(vocab_item, "context_definition_ru", None),
                "source_sentence": getattr(vocab_item, "source_sentence", None),
                "next_review_at": row.next_review_at,
                "error_count": row.error_count,
                "correct_streak": row.correct_streak,
                "status": build_review_status(
                    error_count=row.error_count,
                    correct_streak=row.correct_streak,
                    next_review_at=row.next_review_at,
                    ease_factor=row.ease_factor,
                ).status,
            })
        return items

    def _build_review_session_items_from_vocab(self, *, user_id: int, vocab_items: list, progress_map: dict[int, WordProgressModel]) -> list[dict]:
        now = datetime.utcnow()
        items = []
        for vocab_item in vocab_items:
            if not vocab_item.english_lemma:
                continue
            p = progress_map.get(vocab_item.id)
            error_count = p.error_count if p else 0
            correct_streak = p.correct_streak if p else 0
            ease_factor = p.ease_factor if p else _SM2_EASE_DEFAULT
            next_review_at = p.next_review_at if p else now
            items.append({
                "word": vocab_item.english_lemma,
                "vocabulary_id": vocab_item.id,
                "russian_translation": vocab_item.russian_translation,
                "context_definition": getattr(vocab_item, "context_definition_ru", None),
                "source_sentence": getattr(vocab_item, "source_sentence", None),
                "next_review_at": next_review_at,
                "error_count": error_count,
                "correct_streak": correct_streak,
                "status": build_review_status(
                    error_count=error_count,
                    correct_streak=correct_streak,
                    next_review_at=next_review_at,
                    ease_factor=ease_factor,
                ).status,
            })
        return items

    def _row_to_progress_dict(self, row: WordProgressModel, vocab_map: dict, user_id: int) -> dict:
        vocab_item = vocab_map.get(row.vocabulary_id)
        return {
            "user_id": user_id,
            "word": vocab_item.english_lemma if vocab_item is not None else None,
            "vocabulary_id": row.vocabulary_id,
            "russian_translation": vocab_item.russian_translation if vocab_item is not None else None,
            "error_count": row.error_count,
            "correct_streak": row.correct_streak,
            "next_review_at": row.next_review_at,
            "status": build_review_status(
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                ease_factor=row.ease_factor,
            ).status,
        }


def get_srs_service(srs: SRSService = Depends()) -> SRSService:
    from app.modules.training.service.submission import SubmissionService
    from app.modules.training.repository import TrainingRepository
    from app.modules.graph.repository import GraphRepository
    from app.modules.graph.service.graph import GraphService
    from app.modules.identity.repository import IdentityRepository
    submission = SubmissionService(
        training_repo=TrainingRepository(srs._repo._db),
        srs_service=srs,
        graph_service=GraphService(
            GraphRepository(srs._repo._db),
            IdentityService(IdentityRepository(srs._repo._db)),
        ),
    )
    srs.set_submission_service(submission)
    return srs
