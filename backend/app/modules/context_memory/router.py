from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.context_memory.application_service import context_memory_application_service
from app.modules.context_memory.contracts import (
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
from app.modules.context_memory.schemas import (
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

router = APIRouter(prefix="/context", tags=["context_memory"])


def _to_review_queue_item_response(item: ReviewQueueItemDTO):
    from app.modules.context_memory.schemas import ReviewQueueItem

    return ReviewQueueItem(
        word=item.word,
        russian_translation=item.russian_translation,
        next_review_at=item.next_review_at,
        error_count=item.error_count,
        correct_streak=item.correct_streak,
        status=item.status,
    )


def _to_word_progress_response(item: WordProgressDTO) -> WordProgressRead:
    return WordProgressRead(
        user_id=item.user_id,
        word=item.word,
        russian_translation=item.russian_translation,
        error_count=item.error_count,
        correct_streak=item.correct_streak,
        next_review_at=item.next_review_at,
        status=item.status,
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
        status=item.status,
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


@router.get("/me/review-queue", response_model=ReviewQueueResponse)
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


@router.post("/me/review-queue/submit", response_model=WordProgressRead)
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


@router.post("/me/review-queue/submit-bulk", response_model=ReviewQueueBulkSubmitResponse)
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


@router.post("/me/review-session/start", response_model=ReviewSessionStartResponse)
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


@router.get("/me/word-progress/{word}", response_model=WordProgressRead)
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


@router.delete("/me/word-progress/{word}", response_model=WordProgressDeleteResponse)
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


@router.get("/me/review-plan", response_model=ReviewPlanResponse)
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


@router.get("/me/progress", response_model=ProgressSnapshot)
def progress_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProgressSnapshot:
    result = context_memory_application_service.get_progress_snapshot(
        db=db,
        user_id=None,
        current_user_id=current_user_id,
    )
    return ProgressSnapshot(
        user_id=result.user_id,
        total_sessions=result.total_sessions,
        avg_accuracy=result.avg_accuracy,
    )


@router.get("/me/review-summary", response_model=ReviewSummary)
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
    return ReviewSummary(
        user_id=result.user_id,
        total_tracked=result.total_tracked,
        due_now=result.due_now,
        mastered=result.mastered,
        troubled=result.troubled,
    )
