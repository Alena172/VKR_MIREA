from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ReviewStatus = Literal["due", "upcoming", "mastered", "troubled"]
ReviewStatusFilter = Literal["all", "due", "upcoming", "mastered", "troubled"]


@dataclass(frozen=True)
class ReviewStatusSnapshot:
    status: ReviewStatus
    priority: int
    is_due: bool
    is_mastered: bool
    is_troubled: bool


def build_review_status(
    *,
    error_count: int,
    correct_streak: int,
    next_review_at,
    min_streak: int = 3,
    min_errors: int = 3,
    now: datetime | None = None,
) -> ReviewStatusSnapshot:
    current_time = now or datetime.utcnow()
    is_due = next_review_at <= current_time
    is_troubled = error_count >= min_errors
    is_mastered = correct_streak >= min_streak

    if is_troubled:
        return ReviewStatusSnapshot(
            status="troubled",
            priority=5,
            is_due=is_due,
            is_mastered=is_mastered,
            is_troubled=True,
        )
    if is_due:
        return ReviewStatusSnapshot(
            status="due",
            priority=4,
            is_due=True,
            is_mastered=is_mastered,
            is_troubled=False,
        )
    if is_mastered:
        return ReviewStatusSnapshot(
            status="mastered",
            priority=1,
            is_due=False,
            is_mastered=True,
            is_troubled=False,
        )
    return ReviewStatusSnapshot(
        status="upcoming",
        priority=3,
        is_due=False,
        is_mastered=False,
        is_troubled=False,
    )


def matches_review_status_filter(
    *,
    status_filter: ReviewStatusFilter,
    error_count: int,
    correct_streak: int,
    next_review_at,
    min_streak: int = 3,
    min_errors: int = 3,
    now: datetime | None = None,
) -> bool:
    if status_filter == "all":
        return True
    snapshot = build_review_status(
        error_count=error_count,
        correct_streak=correct_streak,
        next_review_at=next_review_at,
        min_streak=min_streak,
        min_errors=min_errors,
        now=now,
    )
    return snapshot.status == status_filter
