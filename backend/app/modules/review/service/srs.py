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
from app.modules.review.repository import ReviewRepository, _normalize_valid_word
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
    word: str
    is_correct: bool
    vocabulary_id: int | None = None


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

    def submit_review_queue_item(
        self,
        *,
        user_id: int,
        current_user_id: int,
        payload,
    ) -> WordProgressModel:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        normalized = _normalize_valid_word(payload.word)
        if normalized is None:
            raise HTTPException(status_code=400, detail="Word must be a single english token")
        progress = self.apply_review(
            user_id=user_id,
            word=normalized,
            is_correct=payload.is_correct,
            vocabulary_id=payload.vocabulary_id,
        )
        return progress

    def submit_review_queue_bulk(
        self,
        *,
        user_id: int,
        current_user_id: int,
        payload,
    ) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        if not payload.items:
            return {"user_id": user_id, "updated": []}
        updated_rows: list[WordProgressModel] = []
        for item in payload.items:
            normalized = _normalize_valid_word(item.word)
            if normalized is None:
                continue
            progress = self.apply_review(
                user_id=user_id,
                word=normalized,
                is_correct=item.is_correct,
                vocabulary_id=getattr(item, "vocabulary_id", None),
            )
            if progress is not None:
                updated_rows.append(progress)
        return {"user_id": user_id, "updated": updated_rows}

    def start_review_session(
        self,
        *,
        user_id: int,
        current_user_id: int,
        payload,
    ) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        if payload.mode == "srs":
            return self._build_srs_review_session(user_id=user_id, size=payload.size)
        return self._build_random_review_session(user_id=user_id, size=payload.size)

    def _build_srs_review_session(self, *, user_id: int, size: int) -> dict:
        due_rows = self._repo.list_due_word_progress(user_id=user_id, limit=size * 5)
        # Каждая due_row — отдельная карточка (свой vocabulary_id)
        due_rows = due_rows[:size]
        items = self._build_review_session_items_from_progress(user_id=user_id, rows=due_rows)
        return {"user_id": user_id, "mode": "srs", "total_items": len(items), "items": items}

    def _build_random_review_session(self, *, user_id: int, size: int) -> dict:
        vocabulary_items = self._vocab().list_user_items(user_id=user_id)
        valid_items = [
            item for item in vocabulary_items
            if _normalize_valid_word(item.english_lemma)
        ]
        if not valid_items:
            return {"user_id": user_id, "mode": "random", "total_items": 0, "items": []}
        sampled = secrets.SystemRandom().sample(valid_items, k=min(size, len(valid_items)))
        vocab_ids = [item.id for item in sampled]
        progress_map = self._repo.get_progress_map_by_vocabulary_ids(user_id=user_id, vocabulary_ids=vocab_ids)
        items = self._build_review_session_items_from_vocab(
            user_id=user_id, vocab_items=sampled, progress_map=progress_map
        )
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
        rows = self._repo.list_word_progress(
            user_id=user_id, limit=10000, offset=0, q=q, sort_by=sort_by, sort_order=sort_order,
        )
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
            ]
        total = len(rows)
        page_rows = rows[offset:offset + limit]
        translation_map = self._vocab().get_translation_map_for_user(user_id=user_id, english_lemmas=[r.word for r in page_rows])
        items = [self._row_to_progress_dict(row, translation_map, user_id) for row in page_rows]
        return {"user_id": user_id, "total": total, "limit": limit, "offset": offset, "items": items}

    def get_word_progress(self, *, user_id: int, current_user_id: int, word: str) -> WordProgressModel:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        progress = self._repo.get_word_progress(user_id=user_id, word=word)
        if progress is None:
            raise HTTPException(status_code=404, detail="Word progress not found")
        return progress

    def delete_word_progress(self, *, user_id: int, current_user_id: int, word: str) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        deleted = self._repo.delete_word_progress(user_id=user_id, word=word)
        return {
            "user_id": user_id,
            "word": word.strip().lower(),
            "progress_deleted": deleted,
            "removed_from_difficult_words": deleted,
        }

    def get_review_plan(
        self,
        *,
        user_id: int,
        current_user_id: int,
        limit: int,
        horizon_hours: int,
    ) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        due_progress = self._repo.list_due_word_progress(user_id=user_id, limit=limit)
        upcoming_progress = self._repo.list_upcoming_word_progress(
            user_id=user_id, horizon=timedelta(hours=horizon_hours), limit=limit,
        )
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

    def get_review_summary(
        self,
        *,
        user_id: int,
        current_user_id: int,
        min_streak: int,
    ) -> dict:
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
        word: str,
        is_correct: bool,
        vocabulary_id: int | None = None,
    ) -> WordProgressModel | None:
        normalized = _normalize_valid_word(word)
        if not normalized:
            return None
        now = datetime.utcnow()
        row = self._repo.get_or_create_word_progress(
            user_id, normalized, vocabulary_id=vocabulary_id, now=now
        )

        if is_correct:
            new_streak = row.correct_streak + 1
            new_ease = row.ease_factor + _SM2_EASE_CORRECT_DELTA
            new_interval = _sm2_next_interval(
                interval_days=row.interval_days,
                ease_factor=new_ease,
                correct_streak=new_streak,
            )
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

    def ensure_word_progress_entry(
        self, *, user_id: int, word: str, vocabulary_id: int | None = None
    ) -> bool:
        return self._repo.ensure_word_progress(
            user_id=user_id, word=word, vocabulary_id=vocabulary_id
        ) is not None

    def update_learning_progress(
        self,
        *,
        user_id: int,
        updates: list[WordProgressUpdate],
    ) -> list[str]:
        updated_words: list[str] = []
        for update in updates:
            if update.word:
                progress = self.apply_review(
                    user_id=user_id,
                    word=update.word,
                    is_correct=update.is_correct,
                    vocabulary_id=update.vocabulary_id,
                )
                if progress is not None:
                    updated_words.append(progress.word)
        return _dedupe_keep_order(updated_words)

    def get_recommendations(
        self,
        *,
        user_id: int,
        current_user_id: int,
        limit: int,
    ) -> dict:
        self._ensure_user_access(user_id=user_id, current_user_id=current_user_id)
        snapshot = self._scoring.build_snapshot(user_id=user_id, limit=limit)
        words = snapshot.ranked_words(limit)

        recent_error_words = []
        recent_errors_raw = (
            self._submission_service.list_recent_incorrect_words(user_id=user_id, limit=limit * 5, unique=True)
            if self._submission_service is not None
            else []
        )
        for w in recent_errors_raw:
            if _normalize_valid_word(w) and w not in recent_error_words:
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
        difficult_words = [row.word for row in troubled_rows if _normalize_valid_word(row.word)][:limit]

        all_words = list(dict.fromkeys(words + recent_error_words + difficult_words))[:limit * 2]
        progress_map = self._repo.get_word_progress_map(user_id=user_id, words=all_words)
        next_review_at = {
            w: progress_map[w].next_review_at.isoformat() if w in progress_map else None
            for w in all_words
        }
        scores = {w: snapshot.scores.get(w, 0.0) for w in all_words}

        return {
            "user_id": user_id,
            "words": words,
            "recent_error_words": recent_error_words,
            "difficult_words": difficult_words,
            "scores": scores,
            "next_review_at": next_review_at,
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
        difficult_words = [row.word for row in troubled_rows if _normalize_valid_word(row.word)]
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
        return {
            row.word.strip().lower()
            for row in rows
            if row.word
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
        words = [row.word for row in rows]
        translation_map = self._vocab().get_translation_map_for_user(user_id=user_id, english_lemmas=words)
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
                    ease_factor=row.ease_factor,
                ).status,
            }
            for row in rows
            if _normalize_valid_word(row.word) is not None
        ]

    def _build_review_session_items_from_progress(
        self,
        *,
        user_id: int,
        rows: list[WordProgressModel],
    ) -> list[dict]:
        """SRS mode: build session items from existing word_progress rows.

        Fetches per-card translation via vocabulary_id when available.
        """
        vocab_ids = [r.vocabulary_id for r in rows if r.vocabulary_id is not None]
        vocab_map = (
            {item.id: item for item in self._vocab().list_user_items(user_id=user_id)}
            if vocab_ids
            else {}
        )
        word_translation_map: dict[str, str] = {}
        words_without_vid = [r.word for r in rows if r.vocabulary_id is None]
        if words_without_vid:
            word_translation_map = self._vocab().get_translation_map_for_user(
                user_id=user_id, english_lemmas=words_without_vid
            )
        items = []
        for row in rows:
            if _normalize_valid_word(row.word) is None:
                continue
            if row.vocabulary_id is not None and row.vocabulary_id in vocab_map:
                vocab_item = vocab_map[row.vocabulary_id]
                translation = vocab_item.russian_translation
                definition = vocab_item.context_definition_ru
            else:
                translation = word_translation_map.get(row.word)
                definition = None
            items.append({
                "word": row.word,
                "vocabulary_id": row.vocabulary_id,
                "russian_translation": translation,
                "context_definition": definition,
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

    def _build_review_session_items_from_vocab(
        self,
        *,
        user_id: int,
        vocab_items: list,
        progress_map: dict[int, WordProgressModel],
    ) -> list[dict]:
        """Random mode: build session items from vocabulary entries with their own progress."""
        now = datetime.utcnow()
        items = []
        for vocab_item in vocab_items:
            if _normalize_valid_word(vocab_item.english_lemma) is None:
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
                ease_factor=row.ease_factor,
            ).status,
        }


def get_srs_service(
    srs: SRSService = Depends(),
) -> SRSService:
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
