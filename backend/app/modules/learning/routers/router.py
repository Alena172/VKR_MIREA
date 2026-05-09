from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.identity.deps import get_current_user_id
from app.modules.learning.routers.review_presenters import (
    to_progress_snapshot_response,
    to_review_plan_response,
    to_review_queue_bulk_submit_response,
    to_review_queue_response,
    to_review_session_start_response,
    to_review_summary_response,
    to_word_progress_delete_response,
    to_word_progress_list_response,
    to_word_progress_response,
)
from app.modules.learning.schemas.review_schemas import (
    ProgressSnapshot,
    ReviewPlanResponse,
    ReviewQueueBulkSubmitRequest,
    ReviewQueueBulkSubmitResponse,
    ReviewQueueResponse,
    ReviewQueueSubmitRequest,
    ReviewSessionStartRequest,
    ReviewSessionStartResponse,
    ReviewSummary,
    WordProgressDeleteResponse,
    WordProgressListResponse,
    WordProgressRead,
)
from app.modules.learning.services.review_service import context_memory_application_service


router = APIRouter()
@router.get("/context/me/review-queue", response_model=ReviewQueueResponse)
def get_review_queue_me(
    limit: int = Query(default=20, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    return _to_review_queue_response(
        context_memory_application_service.get_review_queue(
            db=db,
            user_id=current_user_id,
            current_user_id=current_user_id,
            limit=limit,
        )
    )


@router.post("/context/me/review-queue/submit", response_model=WordProgressRead)
def submit_review_queue_item_me(
    payload: ReviewQueueSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressRead:
    return _to_word_progress_response(
        context_memory_application_service.submit_review_queue_item(
            db=db,
            user_id=current_user_id,
            current_user_id=current_user_id,
            payload=payload,
        )
    )


@router.post("/context/me/review-queue/submit-bulk", response_model=ReviewQueueBulkSubmitResponse)
def submit_review_queue_bulk_me(
    payload: ReviewQueueBulkSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewQueueBulkSubmitResponse:
    return _to_review_queue_bulk_submit_response(
        context_memory_application_service.submit_review_queue_bulk(
            db=db,
            user_id=current_user_id,
            current_user_id=current_user_id,
            payload=payload,
        )
    )


@router.post("/context/me/review-session/start", response_model=ReviewSessionStartResponse)
def start_review_session_me(
    payload: ReviewSessionStartRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewSessionStartResponse:
    return _to_review_session_start_response(
        context_memory_application_service.start_review_session(
            db=db,
            user_id=current_user_id,
            current_user_id=current_user_id,
            payload=payload,
        )
    )


@router.get("/context/me/word-progress", response_model=WordProgressListResponse)
def list_word_progress_me(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Literal["all", "due", "upcoming", "mastered", "troubled"] = Query(default="all"),
    q: str | None = Query(default=None, max_length=200),
    sort_by: Literal["next_review_at", "error_count", "correct_streak"] = Query(default="next_review_at"),
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
    min_streak: int = Query(default=3, ge=1, le=50),
    min_errors: int = Query(default=3, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressListResponse:
    return _to_word_progress_list_response(
        context_memory_application_service.list_word_progress(
            db=db,
            user_id=current_user_id,
            current_user_id=current_user_id,
            limit=limit,
            offset=offset,
            status=status,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            min_streak=min_streak,
            min_errors=min_errors,
        )
    )


@router.get("/context/me/word-progress/{word}", response_model=WordProgressRead)
def get_word_progress_me(
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressRead:
    return _to_word_progress_response(
        context_memory_application_service.get_word_progress(
            db=db,
            user_id=current_user_id,
            current_user_id=current_user_id,
            word=word,
        )
    )


@router.delete("/context/me/word-progress/{word}", response_model=WordProgressDeleteResponse)
def delete_word_progress_me(
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressDeleteResponse:
    return _to_word_progress_delete_response(
        context_memory_application_service.delete_word_progress(
            db=db,
            user_id=current_user_id,
            current_user_id=current_user_id,
            word=word,
        )
    )


@router.get("/context/me/review-plan", response_model=ReviewPlanResponse)
def get_review_plan_me(
    limit: int = Query(default=10, ge=1, le=100),
    horizon_hours: int = Query(default=24, ge=1, le=168),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewPlanResponse:
    return _to_review_plan_response(
        context_memory_application_service.get_review_plan(
            db=db,
            user_id=current_user_id,
            current_user_id=current_user_id,
            limit=limit,
            horizon_hours=horizon_hours,
        )
    )


@router.get("/context/me/progress", response_model=ProgressSnapshot)
def progress_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProgressSnapshot:
    result = context_memory_application_service.get_progress_snapshot(
        db=db,
        user_id=None,
        current_user_id=current_user_id,
    )
    return to_progress_snapshot_response(result)


@router.get("/context/me/review-summary", response_model=ReviewSummary)
def review_summary_me(
    min_streak: int = Query(default=3, ge=1, le=50),
    min_errors: int = Query(default=3, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewSummary:
    result = context_memory_application_service.get_review_summary(
        db=db,
        user_id=current_user_id,
        current_user_id=current_user_id,
        min_streak=min_streak,
        min_errors=min_errors,
    )
    return to_review_summary_response(result)
