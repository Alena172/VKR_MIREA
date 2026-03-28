from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.context_memory.application_service import context_memory_application_service
from app.modules.context_memory.repository import context_repository
from app.modules.context_memory.schemas import (
    ContextGarbageCleanupResponse,
    ContextRecommendations,
    ProgressSnapshot,
    ReviewPlanResponse,
    ReviewQueueBulkSubmitRequest,
    ReviewQueueBulkSubmitResponse,
    ReviewQueueResponse,
    ReviewQueueSubmitRequest,
    ReviewSessionStartRequest,
    ReviewSessionStartResponse,
    ReviewSummary,
    UserContext,
    UserContextUpsert,
    WordProgressDeleteResponse,
    WordProgressListResponse,
    WordProgressRead,
)
router = APIRouter(prefix="/context", tags=["context_memory"])


@router.get("/me", response_model=UserContext)
def get_context_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserContext:
    return get_context(user_id=current_user_id, current_user_id=current_user_id, db=db)


@router.put("/me", response_model=UserContext)
def upsert_context_me(
    payload: UserContextUpsert,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserContext:
    return upsert_context(user_id=current_user_id, payload=payload, current_user_id=current_user_id, db=db)


@router.get("/me/recommendations", response_model=ContextRecommendations)
def get_recommendations_me(
    limit: int = Query(default=10, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ContextRecommendations:
    return get_recommendations(
        user_id=current_user_id,
        limit=limit,
        current_user_id=current_user_id,
        db=db,
    )


@router.get("/me/review-queue", response_model=ReviewQueueResponse)
def get_review_queue_me(
    limit: int = Query(default=20, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    return get_review_queue(
        user_id=current_user_id,
        limit=limit,
        current_user_id=current_user_id,
        db=db,
    )


@router.post("/me/review-queue/submit", response_model=WordProgressRead)
def submit_review_queue_item_me(
    payload: ReviewQueueSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressRead:
    return submit_review_queue_item(
        user_id=current_user_id,
        payload=payload,
        current_user_id=current_user_id,
        db=db,
    )


@router.post("/me/review-queue/submit-bulk", response_model=ReviewQueueBulkSubmitResponse)
def submit_review_queue_bulk_me(
    payload: ReviewQueueBulkSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewQueueBulkSubmitResponse:
    return submit_review_queue_bulk(
        user_id=current_user_id,
        payload=payload,
        current_user_id=current_user_id,
        db=db,
    )


@router.post("/me/review-session/start", response_model=ReviewSessionStartResponse)
def start_review_session_me(
    payload: ReviewSessionStartRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewSessionStartResponse:
    return start_review_session(
        user_id=current_user_id,
        payload=payload,
        current_user_id=current_user_id,
        db=db,
    )


@router.get("/me/word-progress", response_model=WordProgressListResponse)
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
    return list_word_progress(
        user_id=current_user_id,
        limit=limit,
        offset=offset,
        status=status,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        min_streak=min_streak,
        min_errors=min_errors,
        current_user_id=current_user_id,
        db=db,
    )


@router.get("/me/word-progress/{word}", response_model=WordProgressRead)
def get_word_progress_me(
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressRead:
    return get_word_progress(user_id=current_user_id, word=word, current_user_id=current_user_id, db=db)


@router.delete("/me/word-progress/{word}", response_model=WordProgressDeleteResponse)
def delete_word_progress_me(
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressDeleteResponse:
    return delete_word_progress(user_id=current_user_id, word=word, current_user_id=current_user_id, db=db)


@router.get("/me/review-plan", response_model=ReviewPlanResponse)
def get_review_plan_me(
    limit: int = Query(default=10, ge=1, le=100),
    horizon_hours: int = Query(default=24, ge=1, le=168),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewPlanResponse:
    return get_review_plan(
        user_id=current_user_id,
        limit=limit,
        horizon_hours=horizon_hours,
        current_user_id=current_user_id,
        db=db,
    )


@router.post("/me/cleanup-garbage", response_model=ContextGarbageCleanupResponse)
def cleanup_context_garbage_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ContextGarbageCleanupResponse:
    return cleanup_context_garbage(user_id=current_user_id, current_user_id=current_user_id, db=db)


@router.get("/me/progress", response_model=ProgressSnapshot)
def progress_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProgressSnapshot:
    return progress(user_id=None, current_user_id=current_user_id, db=db)


@router.get("/me/review-summary", response_model=ReviewSummary)
def review_summary_me(
    min_streak: int = Query(default=3, ge=1, le=50),
    min_errors: int = Query(default=3, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewSummary:
    return review_summary(
        user_id=current_user_id,
        min_streak=min_streak,
        min_errors=min_errors,
        current_user_id=current_user_id,
        db=db,
    )


@router.get("/progress", response_model=ProgressSnapshot)
def progress(
    user_id: int | None = Query(default=None, ge=1),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProgressSnapshot:
    target_user_id, total, avg = context_memory_application_service.get_progress_snapshot(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
    )
    return ProgressSnapshot(
        user_id=target_user_id,
        total_sessions=total,
        avg_accuracy=avg,
    )


@router.get("/review-summary", response_model=ReviewSummary)
def review_summary(
    user_id: int = Query(ge=1),
    min_streak: int = Query(default=3, ge=1, le=50),
    min_errors: int = Query(default=3, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewSummary:
    return context_memory_application_service.get_review_summary(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        min_streak=min_streak,
        min_errors=min_errors,
    )


@router.get("/{user_id}", response_model=UserContext)
def get_context(
    user_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserContext:
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    context = context_repository.get_by_user_id(db, user_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Context not found")
    return context


@router.put("/{user_id}", response_model=UserContext)
def upsert_context(
    user_id: int,
    payload: UserContextUpsert,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserContext:
    context_memory_application_service.ensure_user_access(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
    )
    return context_repository.upsert(db, user_id, payload)


@router.get("/{user_id}/recommendations", response_model=ContextRecommendations)
def get_recommendations(
    user_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ContextRecommendations:
    return context_memory_application_service.get_recommendations(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        limit=limit,
    )


@router.get("/{user_id}/review-queue", response_model=ReviewQueueResponse)
def get_review_queue(
    user_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    return context_memory_application_service.get_review_queue(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        limit=limit,
    )


@router.post("/{user_id}/review-queue/submit", response_model=WordProgressRead)
def submit_review_queue_item(
    user_id: int,
    payload: ReviewQueueSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressRead:
    return context_memory_application_service.submit_review_queue_item(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        payload=payload,
    )


@router.post("/{user_id}/review-queue/submit-bulk", response_model=ReviewQueueBulkSubmitResponse)
def submit_review_queue_bulk(
    user_id: int,
    payload: ReviewQueueBulkSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewQueueBulkSubmitResponse:
    return context_memory_application_service.submit_review_queue_bulk(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        payload=payload,
    )


@router.post("/{user_id}/review-session/start", response_model=ReviewSessionStartResponse)
def start_review_session(
    user_id: int,
    payload: ReviewSessionStartRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewSessionStartResponse:
    return context_memory_application_service.start_review_session(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        payload=payload,
    )


@router.get("/{user_id}/word-progress", response_model=WordProgressListResponse)
def list_word_progress(
    user_id: int,
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
    return context_memory_application_service.list_word_progress(
        db=db,
        user_id=user_id,
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


@router.get("/{user_id}/word-progress/{word}", response_model=WordProgressRead)
def get_word_progress(
    user_id: int,
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressRead:
    return context_memory_application_service.get_word_progress(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        word=word,
    )


@router.delete("/{user_id}/word-progress/{word}", response_model=WordProgressDeleteResponse)
def delete_word_progress(
    user_id: int,
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressDeleteResponse:
    return context_memory_application_service.delete_word_progress(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        word=word,
    )


@router.get("/{user_id}/review-plan", response_model=ReviewPlanResponse)
def get_review_plan(
    user_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    horizon_hours: int = Query(default=24, ge=1, le=168),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewPlanResponse:
    return context_memory_application_service.get_review_plan(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        limit=limit,
        horizon_hours=horizon_hours,
    )


@router.post("/{user_id}/cleanup-garbage", response_model=ContextGarbageCleanupResponse)
def cleanup_context_garbage(
    user_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ContextGarbageCleanupResponse:
    return context_memory_application_service.cleanup_context_garbage(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
    )
