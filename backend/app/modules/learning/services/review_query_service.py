from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.modules.learning.models.review_models import WordProgressModel
from app.modules.learning.models.review_status import build_review_status, matches_review_status_filter
from app.modules.learning.repositories.review_repository import context_repository


@dataclass(frozen=True)
class WordProgressListParams:
    limit: int
    offset: int
    status: Literal["all", "due", "upcoming", "mastered", "troubled"]
    q: str | None
    sort_by: Literal["next_review_at", "error_count", "correct_streak"]
    sort_order: Literal["asc", "desc"]
    min_streak: int
    min_errors: int


@dataclass(frozen=True)
class ReviewSummaryCounters:
    total_tracked: int
    due_now: int
    mastered: int
    troubled: int


class ReviewQueryService:
    def list_word_progress_rows(
        self,
        *,
        db,
        user_id: int,
        params: WordProgressListParams,
    ) -> list[WordProgressModel]:
        rows = context_repository.list_word_progress(
            db,
            user_id=user_id,
            limit=10000,
            offset=0,
            q=params.q,
            sort_by=params.sort_by,
            sort_order=params.sort_order,
        )
        if params.status == "all":
            return rows[params.offset:params.offset + params.limit]
        filtered = [
            row for row in rows
            if matches_review_status_filter(
                status_filter=params.status,
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                min_streak=params.min_streak,
                min_errors=params.min_errors,
            )
        ]
        return filtered[params.offset:params.offset + params.limit]

    def count_word_progress_rows(
        self,
        *,
        db,
        user_id: int,
        params: WordProgressListParams,
    ) -> int:
        rows = context_repository.list_word_progress(
            db,
            user_id=user_id,
            limit=10000,
            offset=0,
            q=params.q,
        )
        if params.status == "all":
            return len(rows)
        return sum(
            1
            for row in rows
            if matches_review_status_filter(
                status_filter=params.status,
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                min_streak=params.min_streak,
                min_errors=params.min_errors,
            )
        )

    def build_review_summary_counters(
        self,
        *,
        db,
        user_id: int,
        min_streak: int,
        min_errors: int,
    ) -> ReviewSummaryCounters:
        rows = context_repository.list_word_progress(
            db,
            user_id=user_id,
            limit=10000,
            offset=0,
            q=None,
            sort_by="next_review_at",
            sort_order="asc",
        )
        if not rows:
            return ReviewSummaryCounters(total_tracked=0, due_now=0, mastered=0, troubled=0)
        snapshots = [
            build_review_status(
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                min_streak=min_streak,
                min_errors=min_errors,
            )
            for row in rows
        ]
        return ReviewSummaryCounters(
            total_tracked=len(rows),
            due_now=sum(1 for item in snapshots if item.status == "due"),
            mastered=sum(1 for item in snapshots if item.status == "mastered"),
            troubled=sum(1 for item in snapshots if item.status == "troubled"),
        )


review_query_service = ReviewQueryService()
