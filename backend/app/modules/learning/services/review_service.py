from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.learning.assemblers import (
    to_progress_snapshot_dto,
    to_review_plan_dto,
    to_review_queue_bulk_submit_dto,
    to_review_queue_item_dto,
    to_review_queue_response_dto,
    to_review_summary_dto,
    to_word_progress_delete_dto,
    to_word_progress_list_dto,
)
from app.modules.learning.contracts import (
    ProgressSnapshotDTO,
    ReviewPlanDTO,
    ReviewQueueBulkSubmitDTO,
    ReviewQueueResponseDTO,
    ReviewSessionStartDTO,
    ReviewSummaryDTO,
    WordProgressDTO,
    WordProgressDeleteDTO,
    WordProgressListDTO,
    WordProgressUpdate,
)
from app.modules.learning.models.review_models import WordProgressModel
from app.modules.learning.models.review_status import matches_review_status_filter
from app.modules.learning.repositories.review_repository import context_repository
from app.modules.learning.services.recommendation_scoring_service import recommendation_scoring_service
from app.modules.learning.services.review_projection_service import review_projection_service
from app.modules.learning.services.review_query_service import (
    WordProgressListParams,
    review_query_service,
)
from app.modules.learning.services.review_session_factory import review_session_factory
from app.modules.learning.schemas.review_schemas import (
    ReviewQueueBulkSubmitRequest,
    ReviewQueueSubmitRequest,
    ReviewSessionStartRequest,
)
from app.modules.learning.session_public_api import learning_session_public_api
from app.modules.identity.public_api import users_public_api

_WORD_RE = re.compile(r"^[a-z][a-z'-]{0,48}$")


def _is_valid_review_word(value: str | None) -> bool:
    """Проверяет, что слово подходит для SRS-учета."""

    if not value:
        return False
    return bool(_WORD_RE.fullmatch(value.strip().lower()))


def _dedupe_keep_order(values: list[str]) -> list[str]:
    """Удаляет дубли, сохраняя исходный порядок."""

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
    """Application-сервис SRS, очереди повторения и прогресса слов."""

    def ensure_user_access(self, *, db: Session, user_id: int, current_user_id: int):
        """Проверяет, что пользователь работает только со своими данными."""

        if user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        user = users_public_api.get_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def get_review_queue(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        limit: int,
    ) -> ReviewQueueResponseDTO:
        """Возвращает слова, срок повторения которых уже наступил."""

        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        due_progress = context_repository.list_due_word_progress(db, user_id=user_id, limit=limit * 5)
        total_due_raw = context_repository.count_due_word_progress(db, user_id=user_id)
        items = review_projection_service.build_review_queue_items(
            db=db,
            user_id=user_id,
            rows=due_progress,
            is_valid_word=_is_valid_review_word,
        )[:limit]
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
        """Обновляет прогресс одного слова после ответа в очереди повторения."""

        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)

        normalized_word = payload.word.strip().lower()
        if not _is_valid_review_word(normalized_word):
            raise HTTPException(status_code=400, detail="Word must be a single english token")

        progress = context_repository.update_word_progress(
            db,
            user_id=user_id,
            word=normalized_word,
            is_correct=payload.is_correct,
        )
        if progress is None:
            raise HTTPException(status_code=400, detail="Word is empty")
        db.refresh(progress)
        return review_projection_service.to_word_progress_read(db=db, user_id=user_id, progress=progress)

    def submit_review_queue_bulk(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        payload: ReviewQueueBulkSubmitRequest,
    ) -> ReviewQueueBulkSubmitDTO:
        """Обновляет прогресс сразу по нескольким словам."""

        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)

        if not payload.items:
            return to_review_queue_bulk_submit_dto(user_id=user_id, updated=[])

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
            updated_progress_rows.append(progress)
        updated = review_projection_service.to_word_progress_reads(
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
        """Создает набор карточек для review-сессии."""

        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)

        if payload.mode == "srs":
            return review_session_factory.build_srs_review_session(
                db=db,
                user_id=user_id,
                size=payload.size,
                dedupe_keep_order=_dedupe_keep_order,
                is_valid_word=_is_valid_review_word,
            )

        return review_session_factory.build_random_review_session(
            db=db,
            user_id=user_id,
            size=payload.size,
            dedupe_keep_order=_dedupe_keep_order,
            is_valid_word=_is_valid_review_word,
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
        params = WordProgressListParams(
            limit=limit,
            offset=offset,
            status=status,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            min_streak=min_streak,
            min_errors=min_errors,
        )
        rows = review_query_service.list_word_progress_rows(db=db, user_id=user_id, params=params)
        total = review_query_service.count_word_progress_rows(db=db, user_id=user_id, params=params)
        items = review_projection_service.to_word_progress_reads(db=db, user_id=user_id, progress_rows=rows)
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
        return review_projection_service.to_word_progress_read(db=db, user_id=user_id, progress=progress)

    def delete_word_progress(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        word: str,
    ) -> WordProgressDeleteDTO:
        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        return to_word_progress_delete_dto(
            user_id=user_id,
            word=word.strip().lower(),
            progress_deleted=context_repository.delete_word_progress(db, user_id=user_id, word=word),
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
        """Строит план повторения на сейчас и ближайший горизонт."""

        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)

        due_progress = context_repository.list_due_word_progress(db, user_id=user_id, limit=limit)
        upcoming_progress = context_repository.list_upcoming_word_progress(
            db,
            user_id=user_id,
            horizon=timedelta(hours=horizon_hours),
            limit=limit,
        )
        due_now = review_projection_service.build_review_queue_items(
            db=db,
            user_id=user_id,
            rows=due_progress,
            is_valid_word=_is_valid_review_word,
        )
        upcoming = review_projection_service.build_review_queue_items(
            db=db,
            user_id=user_id,
            rows=upcoming_progress,
            is_valid_word=_is_valid_review_word,
        )
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

    def get_review_summary(
        self,
        *,
        db: Session,
        user_id: int,
        current_user_id: int,
        min_streak: int,
        min_errors: int,
    ) -> ReviewSummaryDTO:
        """Возвращает агрегированную сводку прогресса повторения."""

        self.ensure_user_access(db=db, user_id=user_id, current_user_id=current_user_id)
        counters = review_query_service.build_review_summary_counters(
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
        user = users_public_api.get_by_id(db, user_id)
        return user.cefr_level if user is not None else fallback_cefr

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
        updated_words: list[str] = []

        for update in updates:
            if not update.word:
                continue
            progress = context_repository.update_word_progress(
                db,
                user_id=user_id,
                word=update.word,
                is_correct=update.is_correct,
            )
            if progress is not None:
                updated_words.append(progress.word)

        return _dedupe_keep_order(updated_words)

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

context_memory_application_service = ContextMemoryApplicationService()
