from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import secrets
from typing import Literal

from app.core.application import application_transaction
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.context_memory.assembler import (
    to_context_garbage_cleanup_dto,
    to_context_recommendations_dto,
    to_progress_snapshot_dto,
    to_review_plan_dto,
    to_review_queue_bulk_submit_dto,
    to_review_queue_response_dto,
    to_review_session_item_dto,
    to_review_session_start_dto,
    to_review_summary_dto,
    to_word_progress_delete_dto,
    to_word_progress_dto,
    to_word_progress_list_dto,
)
from app.modules.context_memory.contracts import (
    ContextGarbageCleanupDTO,
    ContextRecommendationsDTO,
    ProgressSnapshotDTO,
    ReviewPlanDTO,
    ReviewQueueBulkSubmitDTO,
    ReviewQueueItemDTO,
    ReviewQueueResponseDTO,
    ReviewSessionItemDTO,
    ReviewSessionStartDTO,
    ReviewSummaryDTO,
    WordProgressDTO,
    WordProgressDeleteDTO,
    WordProgressListDTO,
    WordProgressUpdate,
)
from app.modules.context_memory.models import WordProgressModel
from app.modules.context_memory.recommendation_scoring_service import recommendation_scoring_service
from app.modules.context_memory.repository import context_repository
from app.modules.context_memory.schemas import (
    ReviewQueueBulkSubmitRequest,
    ReviewQueueSubmitRequest,
    ReviewSessionStartRequest,
)
from app.modules.learning_session.public_api import learning_session_public_api
from app.modules.users.public_api import users_public_api
from app.modules.vocabulary.public_api import vocabulary_public_api

_WORD_RE = re.compile(r"^[a-z][a-z'-]{0,48}$")


@dataclass(frozen=True)
class _WordProgressListParams:
    limit: int
    offset: int
    status: Literal["all", "due", "upcoming", "mastered", "troubled"]
    q: str | None
    sort_by: Literal["next_review_at", "error_count", "correct_streak"]
    sort_order: Literal["asc", "desc"]
    min_streak: int
    min_errors: int


@dataclass(frozen=True)
class _ReviewSummaryCounters:
    total_tracked: int
    due_now: int
    mastered: int
    troubled: int


def _is_valid_review_word(value: str | None) -> bool:
    if not value:
        return False
    return bool(_WORD_RE.fullmatch(value.strip().lower()))


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


class ContextMemoryApplicationService:
    def ensure_user_access(self, *, db: Session, user_id: int, current_user_id: int):
        if user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        user = users_public_api.get_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def get_recommendations(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        limit: int,
    ) -> ContextRecommendationsDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)

        snapshot = recommendation_scoring_service.build_snapshot(
            db=db,
            user_id=user_id,
            limit=limit,
        )
        words = snapshot.ranked_words(limit)

        recent_error_words: list[str] = []
        for word in snapshot.recent_error_words_stream:
            if word not in recent_error_words:
                recent_error_words.append(word)
            if len(recent_error_words) >= limit:
                break

        return to_context_recommendations_dto(
            user_id=user_id,
            words=words,
            recent_error_words=recent_error_words,
            difficult_words=snapshot.difficult_words[:limit],
            scores={word: round(snapshot.scores[word], 6) for word in words},
            next_review_at={
                word: snapshot.due_progress_map.get(word).next_review_at if snapshot.due_progress_map.get(word) else None
                for word in words
            },
        )

    def get_review_queue(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        limit: int,
    ) -> ReviewQueueResponseDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        due_progress = context_repository.list_due_word_progress(db, user_id=user_id, limit=limit * 5)
        total_due_raw = context_repository.count_due_word_progress(db, user_id=user_id)
        items = self._build_review_queue_items(db=db, user_id=user_id, rows=due_progress)[:limit]
        total_due = min(total_due_raw, len(items))
        return to_review_queue_response_dto(user_id=user_id, total_due=total_due, items=items)

    def submit_review_queue_item(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        payload: ReviewQueueSubmitRequest,
    ) -> WordProgressDTO:
        user = self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)

        normalized_word = payload.word.strip().lower()
        if not _is_valid_review_word(normalized_word):
            raise HTTPException(status_code=400, detail="Word must be a single english token")

        with application_transaction.boundary(db=db):
            progress = context_repository.update_word_progress(
                db,
                user_id=user_id,
                word=normalized_word,
                is_correct=payload.is_correct,
            )
            if progress is None:
                raise HTTPException(status_code=400, detail="Word is empty")

            if not payload.is_correct:
                context_repository.add_difficult_words(
                    db,
                    user_id=user_id,
                    words=[normalized_word],
                    default_cefr_level=user.cefr_level,
                    auto_commit=False,
                )
        db.refresh(progress)
        return self._to_word_progress_read(db=db, user_id=user_id, progress=progress)

    def submit_review_queue_bulk(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        payload: ReviewQueueBulkSubmitRequest,
    ) -> ReviewQueueBulkSubmitDTO:
        user = self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)

        if not payload.items:
            return to_review_queue_bulk_submit_dto(user_id=user_id, updated=[])

        with application_transaction.boundary(db=db):
            incorrect_words: list[str] = []
            updated_progress_rows: list[WordProgressModel] = []
            for item in payload.items:
                normalized_word = item.word.strip().lower()
                if not _is_valid_review_word(normalized_word):
                    continue
                progress = context_repository.update_word_progress(
                    db,
                    user_id=user_id,
                    word=normalized_word,
                    is_correct=item.is_correct,
                )
                if progress is None:
                    continue

                if not item.is_correct:
                    incorrect_words.append(normalized_word)
                updated_progress_rows.append(progress)

            if incorrect_words:
                context_repository.add_difficult_words(
                    db,
                    user_id=user_id,
                    words=incorrect_words,
                    default_cefr_level=user.cefr_level,
                    auto_commit=False,
                )
        updated = self._to_word_progress_reads(
            db=db,
            user_id=user_id,
            progress_rows=updated_progress_rows,
        )
        return to_review_queue_bulk_submit_dto(user_id=user_id, updated=updated)

    def start_review_session(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        payload: ReviewSessionStartRequest,
    ) -> ReviewSessionStartDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)

        if payload.mode == "srs":
            return self._build_srs_review_session(
                db=db,
                user_id=user_id,
                size=payload.size,
            )

        return self._build_random_review_session(
            db=db,
            user_id=user_id,
            size=payload.size,
        )

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
    ) -> WordProgressListDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        params = _WordProgressListParams(
            limit=limit,
            offset=offset,
            status=status,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            min_streak=min_streak,
            min_errors=min_errors,
        )
        rows = self._list_word_progress_rows(db=db, user_id=user_id, params=params)
        total = self._count_word_progress_rows(db=db, user_id=user_id, params=params)
        items = self._to_word_progress_reads(db=db, user_id=user_id, progress_rows=rows)
        return to_word_progress_list_dto(
            user_id=user_id,
            total=total,
            limit=params.limit,
            offset=params.offset,
            items=items,
        )

    def get_word_progress(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        word: str,
    ) -> WordProgressDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        progress = context_repository.get_word_progress(db, user_id=user_id, word=word)
        if progress is None:
            raise HTTPException(status_code=404, detail="Word progress not found")
        return self._to_word_progress_read(db=db, user_id=user_id, progress=progress)

    def delete_word_progress(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        word: str,
    ) -> WordProgressDeleteDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        with application_transaction.boundary(db=db):
            progress_deleted = context_repository.delete_word_progress(db, user_id=user_id, word=word)
            removed_from_difficult_words = context_repository.remove_difficult_word(db, user_id=user_id, word=word)
        return to_word_progress_delete_dto(
            user_id=user_id,
            word=word.strip().lower(),
            progress_deleted=progress_deleted,
            removed_from_difficult_words=removed_from_difficult_words,
        )

    def get_review_plan(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        limit: int,
        horizon_hours: int,
    ) -> ReviewPlanDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)

        due_progress = context_repository.list_due_word_progress(db, user_id=user_id, limit=limit)
        upcoming_progress = context_repository.list_upcoming_word_progress(
            db,
            user_id=user_id,
            horizon=timedelta(hours=horizon_hours),
            limit=limit,
        )
        due_now = self._build_review_queue_items(db=db, user_id=user_id, rows=due_progress)
        upcoming = self._build_review_queue_items(db=db, user_id=user_id, rows=upcoming_progress)
        snapshot = recommendation_scoring_service.build_snapshot(
            db=db,
            user_id=user_id,
            limit=limit,
        )

        return to_review_plan_dto(
            user_id=user_id,
            due_count=len(due_now),
            upcoming_count=len(upcoming),
            due_now=due_now,
            upcoming=upcoming,
            recommended_words=snapshot.ranked_words(limit),
        )

    def cleanup_context_garbage(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
    ) -> ContextGarbageCleanupDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        with application_transaction.boundary(db=db):
            vocabulary_words = self._list_vocabulary_review_words(db=db, user_id=user_id)
            removed_word_progress, removed_difficult_words = context_repository.cleanup_user_garbage(
                db,
                user_id=user_id,
                vocabulary_words=vocabulary_words,
            )
        return to_context_garbage_cleanup_dto(
            user_id=user_id,
            removed_word_progress=removed_word_progress,
            removed_difficult_words=removed_difficult_words,
        )

    def get_review_summary(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        min_streak: int,
        min_errors: int,
    ) -> ReviewSummaryDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        counters = self._build_review_summary_counters(
            db=db,
            user_id=user_id,
            min_streak=min_streak,
            min_errors=min_errors,
        )

        return to_review_summary_dto(
            user_id=user_id,
            total_tracked=counters.total_tracked,
            due_now=counters.due_now,
            mastered=counters.mastered,
            troubled=counters.troubled,
        )

    def get_effective_cefr_level(
        self,
        *,
        db: Session,
        user_id: int,
        fallback_cefr: str,
    ) -> str:
        context = context_repository.get_by_user_id(db, user_id)
        return context.cefr_level if context is not None else fallback_cefr

    def ensure_word_progress_entry(
        self,
        *,
        db: Session,
        user_id: int,
        word: str,
    ) -> bool:
        return context_repository.ensure_word_progress(db, user_id=user_id, word=word) is not None

    def update_learning_progress(
        self,
        *,
        db: Session,
        user_id: int,
        user_cefr_level: str | None,
        updates: list[WordProgressUpdate],
    ) -> list[str]:
        difficult_words_to_add: list[str] = []

        for update in updates:
            if not update.word:
                continue
            context_repository.update_word_progress(
                db,
                user_id=user_id,
                word=update.word,
                is_correct=update.is_correct,
            )
            if update.mark_difficult:
                difficult_words_to_add.append(update.word)

        context_repository.add_difficult_words(
            db,
            user_id=user_id,
            words=difficult_words_to_add,
            default_cefr_level=user_cefr_level,
            auto_commit=False,
        )
        return difficult_words_to_add

    def get_progress_snapshot(
        self,
        *,
        db: Session,
        user_id: int | None,
        current_user_id: int,
    ) -> ProgressSnapshotDTO:
        if user_id is not None and user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        target_user_id = user_id or current_user_id
        progress = learning_session_public_api.get_progress_dto(
            db,
            user_id=target_user_id,
        )
        return to_progress_snapshot_dto(
            user_id=target_user_id,
            total_sessions=progress.total_sessions,
            avg_accuracy=progress.average_accuracy,
        )

    def _build_review_queue_items(
        self,
        *,
        db: Session,
        user_id: int,
        rows: list[WordProgressModel],
    ) -> list[ReviewQueueItemDTO]:
        words = [row.word for row in rows]
        translation_map = vocabulary_public_api.get_translation_map(db, user_id=user_id, english_lemmas=words)
        return [
            to_review_queue_item_dto(
                word=row.word,
                russian_translation=translation_map.get(row.word),
                next_review_at=row.next_review_at,
                error_count=row.error_count,
                correct_streak=row.correct_streak,
            )
            for row in rows
            if _is_valid_review_word(row.word)
        ]

    def _to_word_progress_reads(
        self,
        *,
        db: Session,
        user_id: int,
        progress_rows: list[WordProgressModel],
    ) -> list[WordProgressDTO]:
        words = [row.word for row in progress_rows]
        translation_map = vocabulary_public_api.get_translation_map(db, user_id=user_id, english_lemmas=words)
        return [
            to_word_progress_dto(
                user_id=row.user_id,
                word=row.word,
                russian_translation=translation_map.get(row.word),
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
            )
            for row in progress_rows
        ]

    def _to_word_progress_read(
        self,
        *,
        db: Session,
        user_id: int,
        progress: WordProgressModel,
    ) -> WordProgressDTO:
        translation_map = vocabulary_public_api.get_translation_map(
            db,
            user_id=user_id,
            english_lemmas=[progress.word],
        )
        return to_word_progress_dto(
            user_id=progress.user_id,
            word=progress.word,
            russian_translation=translation_map.get(progress.word),
            error_count=progress.error_count,
            correct_streak=progress.correct_streak,
            next_review_at=progress.next_review_at,
        )

    def _build_srs_review_session(
        self,
        *,
        db: Session,
        user_id: int,
        size: int,
    ) -> ReviewSessionStartDTO:
        due_rows = context_repository.list_due_word_progress(db, user_id=user_id, limit=size * 5)
        words = _dedupe_keep_order([row.word for row in due_rows if _is_valid_review_word(row.word)])[:size]
        row_map = {row.word: row for row in due_rows}
        items = self._build_review_session_items(
            db=db,
            user_id=user_id,
            words=words,
            progress_map=row_map,
        )
        return to_review_session_start_dto(
            user_id=user_id,
            mode="srs",
            total_items=len(items),
            items=items,
        )

    def _build_random_review_session(
        self,
        *,
        db: Session,
        user_id: int,
        size: int,
    ) -> ReviewSessionStartDTO:
        vocabulary_items = vocabulary_public_api.list_items(db, user_id=user_id)
        unique_words = _dedupe_keep_order(
            [item.english_lemma for item in vocabulary_items if _is_valid_review_word(item.english_lemma)]
        )
        if not unique_words:
            return to_review_session_start_dto(user_id=user_id, mode="random", total_items=0, items=[])

        sample_size = min(size, len(unique_words))
        random_words = secrets.SystemRandom().sample(unique_words, k=sample_size)
        progress_map = context_repository.get_word_progress_map(db, user_id=user_id, words=random_words)
        items = self._build_review_session_items(
            db=db,
            user_id=user_id,
            words=random_words,
            progress_map=progress_map,
        )
        return to_review_session_start_dto(
            user_id=user_id,
            mode="random",
            total_items=len(items),
            items=items,
        )

    def _build_review_session_items(
        self,
        *,
        db: Session,
        user_id: int,
        words: list[str],
        progress_map: dict[str, WordProgressModel],
    ) -> list[ReviewSessionItemDTO]:
        translation_map = vocabulary_public_api.get_translation_map(db, user_id=user_id, english_lemmas=words)
        definition_map = vocabulary_public_api.get_definition_map(db, user_id=user_id, english_lemmas=words)
        return [
            to_review_session_item_dto(
                word=word,
                russian_translation=translation_map.get(word),
                context_definition=definition_map.get(word),
                next_review_at=progress_map[word].next_review_at if word in progress_map else None,
                error_count=progress_map[word].error_count if word in progress_map else 0,
                correct_streak=progress_map[word].correct_streak if word in progress_map else 0,
            )
            for word in words
        ]

    def _list_word_progress_rows(
        self,
        *,
        db: Session,
        user_id: int,
        params: _WordProgressListParams,
    ) -> list[WordProgressModel]:
        return context_repository.list_word_progress(
            db,
            user_id=user_id,
            limit=params.limit,
            offset=params.offset,
            status=params.status,
            q=params.q,
            sort_by=params.sort_by,
            sort_order=params.sort_order,
            min_streak=params.min_streak,
            min_errors=params.min_errors,
        )

    def _count_word_progress_rows(
        self,
        *,
        db: Session,
        user_id: int,
        params: _WordProgressListParams,
    ) -> int:
        return context_repository.count_word_progress(
            db,
            user_id=user_id,
            status=params.status,
            q=params.q,
            min_streak=params.min_streak,
            min_errors=params.min_errors,
        )

    def _list_vocabulary_review_words(
        self,
        *,
        db: Session,
        user_id: int,
    ) -> set[str]:
        return {
            item.english_lemma.strip().lower()
            for item in vocabulary_public_api.list_items(db, user_id=user_id)
            if _is_valid_review_word(item.english_lemma)
        }

    def _build_review_summary_counters(
        self,
        *,
        db: Session,
        user_id: int,
        min_streak: int,
        min_errors: int,
    ) -> _ReviewSummaryCounters:
        vocabulary_words = vocabulary_public_api.list_english_lemmas(db, user_id=user_id)
        if not vocabulary_words:
            return _ReviewSummaryCounters(total_tracked=0, due_now=0, mastered=0, troubled=0)

        base_stmt = select(WordProgressModel).where(
            WordProgressModel.user_id == user_id,
            WordProgressModel.word.in_(vocabulary_words),
        )
        total_tracked = int(db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0)
        now_utc = datetime.utcnow()
        due_now = int(
            db.scalar(
                select(func.count()).select_from(
                    base_stmt.where(WordProgressModel.next_review_at <= now_utc).subquery()
                )
            )
            or 0
        )
        mastered = int(
            db.scalar(
                select(func.count()).select_from(
                    base_stmt.where(WordProgressModel.correct_streak >= min_streak).subquery()
                )
            )
            or 0
        )
        troubled = int(
            db.scalar(
                select(func.count()).select_from(
                    base_stmt.where(WordProgressModel.error_count >= min_errors).subquery()
                )
            )
            or 0
        )
        return _ReviewSummaryCounters(
            total_tracked=total_tracked,
            due_now=due_now,
            mastered=mastered,
            troubled=troubled,
        )


context_memory_application_service = ContextMemoryApplicationService()
