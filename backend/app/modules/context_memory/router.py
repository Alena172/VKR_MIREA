from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.context_memory.application_service import context_memory_application_service
from app.modules.context_memory.contracts import (
    ContextGarbageCleanupDTO,
    ContextRecommendationsDTO,
    ReviewPlanDTO,
    ReviewQueueBulkSubmitDTO,
    ReviewQueueItemDTO,
    ReviewQueueResponseDTO,
    ReviewSessionItemDTO,
    ReviewSessionStartDTO,
    WordProgressDTO,
    WordProgressDeleteDTO,
    WordProgressListDTO,
)
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


def _to_review_queue_item_response(item: ReviewQueueItemDTO):
    from app.modules.context_memory.schemas import ReviewQueueItem

    return ReviewQueueItem(
        word=item.word,
        russian_translation=item.russian_translation,
        next_review_at=item.next_review_at,
        error_count=item.error_count,
        correct_streak=item.correct_streak,
    )


def _to_word_progress_response(item: WordProgressDTO) -> WordProgressRead:
    return WordProgressRead(
        user_id=item.user_id,
        word=item.word,
        russian_translation=item.russian_translation,
        error_count=item.error_count,
        correct_streak=item.correct_streak,
        next_review_at=item.next_review_at,
    )


def _to_context_recommendations_response(result: ContextRecommendationsDTO) -> ContextRecommendations:
    return ContextRecommendations(
        user_id=result.user_id,
        words=result.words,
        recent_error_words=result.recent_error_words,
        difficult_words=result.difficult_words,
        scores=result.scores,
        next_review_at=result.next_review_at,
    )


def _to_review_queue_response(result: ReviewQueueResponseDTO) -> ReviewQueueResponse:
    return ReviewQueueResponse(
        user_id=result.user_id,
        total_due=result.total_due,
        items=[_to_review_queue_item_response(item) for item in result.items],
    )


def _to_review_queue_bulk_submit_response(result: ReviewQueueBulkSubmitDTO) -> ReviewQueueBulkSubmitResponse:
    return ReviewQueueBulkSubmitResponse(
        user_id=result.user_id,
        updated=[_to_word_progress_response(item) for item in result.updated],
    )


def _to_review_session_item_response(item: ReviewSessionItemDTO):
    from app.modules.context_memory.schemas import ReviewSessionItem

    return ReviewSessionItem(
        word=item.word,
        russian_translation=item.russian_translation,
        context_definition=item.context_definition,
        next_review_at=item.next_review_at,
        error_count=item.error_count,
        correct_streak=item.correct_streak,
    )


def _to_review_session_start_response(result: ReviewSessionStartDTO) -> ReviewSessionStartResponse:
    return ReviewSessionStartResponse(
        user_id=result.user_id,
        mode=result.mode,
        total_items=result.total_items,
        items=[_to_review_session_item_response(item) for item in result.items],
    )


def _to_word_progress_list_response(result: WordProgressListDTO) -> WordProgressListResponse:
    return WordProgressListResponse(
        user_id=result.user_id,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        items=[_to_word_progress_response(item) for item in result.items],
    )


def _to_word_progress_delete_response(result: WordProgressDeleteDTO) -> WordProgressDeleteResponse:
    return WordProgressDeleteResponse(
        user_id=result.user_id,
        word=result.word,
        progress_deleted=result.progress_deleted,
        removed_from_difficult_words=result.removed_from_difficult_words,
    )


def _to_review_plan_response(result: ReviewPlanDTO) -> ReviewPlanResponse:
    return ReviewPlanResponse(
        user_id=result.user_id,
        due_count=result.due_count,
        upcoming_count=result.upcoming_count,
        due_now=[_to_review_queue_item_response(item) for item in result.due_now],
        upcoming=[_to_review_queue_item_response(item) for item in result.upcoming],
        recommended_words=result.recommended_words,
    )


def _to_context_garbage_cleanup_response(result: ContextGarbageCleanupDTO) -> ContextGarbageCleanupResponse:
    return ContextGarbageCleanupResponse(
        user_id=result.user_id,
        removed_word_progress=result.removed_word_progress,
        removed_difficult_words=result.removed_difficult_words,
    )


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
    result = context_memory_application_service.get_progress_snapshot(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
    )
    return ProgressSnapshot(
        user_id=result.user_id,
        total_sessions=result.total_sessions,
        avg_accuracy=result.avg_accuracy,
    )


@router.get("/review-summary", response_model=ReviewSummary)
def review_summary(
    user_id: int = Query(ge=1),
    min_streak: int = Query(default=3, ge=1, le=50),
    min_errors: int = Query(default=3, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewSummary:
    result = context_memory_application_service.get_review_summary(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        min_streak=min_streak,
        min_errors=min_errors,
    )
    return ReviewSummary(
        user_id=result.user_id,
        total_tracked=result.total_tracked,
        due_now=result.due_now,
        mastered=result.mastered,
        troubled=result.troubled,
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
    return _to_context_recommendations_response(context_memory_application_service.get_recommendations(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        limit=limit,
    ))


@router.get("/{user_id}/review-queue", response_model=ReviewQueueResponse)
def get_review_queue(
    user_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    return _to_review_queue_response(context_memory_application_service.get_review_queue(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        limit=limit,
    ))


@router.post("/{user_id}/review-queue/submit", response_model=WordProgressRead)
def submit_review_queue_item(
    user_id: int,
    payload: ReviewQueueSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressRead:
    return _to_word_progress_response(context_memory_application_service.submit_review_queue_item(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        payload=payload,
    ))


@router.post("/{user_id}/review-queue/submit-bulk", response_model=ReviewQueueBulkSubmitResponse)
def submit_review_queue_bulk(
    user_id: int,
    payload: ReviewQueueBulkSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewQueueBulkSubmitResponse:
    return _to_review_queue_bulk_submit_response(context_memory_application_service.submit_review_queue_bulk(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        payload=payload,
    ))


@router.post("/{user_id}/review-session/start", response_model=ReviewSessionStartResponse)
def start_review_session(
    user_id: int,
    payload: ReviewSessionStartRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewSessionStartResponse:
    return _to_review_session_start_response(context_memory_application_service.start_review_session(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        payload=payload,
    ))


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
    return _to_word_progress_list_response(context_memory_application_service.list_word_progress(
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
    ))


@router.get("/{user_id}/word-progress/{word}", response_model=WordProgressRead)
def get_word_progress(
    user_id: int,
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressRead:
    return _to_word_progress_response(context_memory_application_service.get_word_progress(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        word=word,
    ))


@router.delete("/{user_id}/word-progress/{word}", response_model=WordProgressDeleteResponse)
def delete_word_progress(
    user_id: int,
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WordProgressDeleteResponse:
    return _to_word_progress_delete_response(context_memory_application_service.delete_word_progress(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        word=word,
    ))


@router.get("/{user_id}/review-plan", response_model=ReviewPlanResponse)
def get_review_plan(
    user_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    horizon_hours: int = Query(default=24, ge=1, le=168),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewPlanResponse:
    return _to_review_plan_response(context_memory_application_service.get_review_plan(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
        limit=limit,
        horizon_hours=horizon_hours,
    ))


@router.post("/{user_id}/cleanup-garbage", response_model=ContextGarbageCleanupResponse)
def cleanup_context_garbage(
    user_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ContextGarbageCleanupResponse:
    return _to_context_garbage_cleanup_response(context_memory_application_service.cleanup_context_garbage(
        db=db,
        user_id=user_id,
        current_user_id=current_user_id,
    ))
