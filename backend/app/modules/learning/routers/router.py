from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.application import AsyncTaskResponse, application_access
from app.core.db import get_db
from app.modules.identity.dependencies import get_current_user_id
from app.modules.identity.public_api import users_public_api
from app.modules.learning.repositories.session_repository import learning_session_repository
from app.modules.learning.schemas.exercise_schemas import ExerciseGenerateRequest, ExerciseGenerateRequestMe
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
from app.modules.learning.schemas.session_schemas import (
    SessionAnswerRead,
    SessionHistoryResponse,
    SessionSubmitRequest,
    SessionSubmitResponse,
    SessionSummary,
)
from app.modules.learning.services.exercise_service import exercise_engine_application_service
from app.modules.learning.services.review_service import context_memory_application_service
from app.modules.learning.services.session_submission_service import learning_session_submission_service
from app.modules.learning.contracts import (
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


router = APIRouter()


@router.post("/exercises/me/generate", response_model=AsyncTaskResponse, status_code=202)
def generate_me(
    payload: ExerciseGenerateRequestMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return exercise_engine_application_service.queue_generation(
        db=db,
        payload=ExerciseGenerateRequest(
            user_id=current_user_id,
            vocabulary_ids=payload.vocabulary_ids,
            size=payload.size,
            fast_start=payload.fast_start,
            incremental=payload.incremental,
            mode=payload.mode,
        ),
        current_user_id=current_user_id,
    )


@router.post("/exercises/generate", response_model=AsyncTaskResponse, status_code=202)
def generate(
    payload: ExerciseGenerateRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return exercise_engine_application_service.queue_generation(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )



@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    user_id: int | None = Query(default=None, ge=1),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[SessionSummary]:
    if user_id is not None and user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return learning_session_repository.list_sessions(db, user_id=user_id or current_user_id)


@router.get("/sessions/me", response_model=SessionHistoryResponse)
def list_my_sessions(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    min_accuracy: float | None = Query(default=None, ge=0.0, le=1.0),
    max_accuracy: float | None = Query(default=None, ge=0.0, le=1.0),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SessionHistoryResponse:
    if min_accuracy is not None and max_accuracy is not None and min_accuracy > max_accuracy:
        raise HTTPException(status_code=400, detail="min_accuracy cannot be greater than max_accuracy")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from cannot be after date_to")

    created_from = datetime.combine(date_from, time.min) if date_from is not None else None
    created_to = datetime.combine(date_to + timedelta(days=1), time.min) if date_to is not None else None

    items = learning_session_repository.list_sessions_paginated(
        db,
        user_id=current_user_id,
        limit=limit,
        offset=offset,
        min_accuracy=min_accuracy,
        max_accuracy=max_accuracy,
        created_from=created_from,
        created_to=created_to,
    )
    total = learning_session_repository.count_sessions(
        db,
        user_id=current_user_id,
        min_accuracy=min_accuracy,
        max_accuracy=max_accuracy,
        created_from=created_from,
        created_to=created_to,
    )
    return SessionHistoryResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/sessions/{session_id}/answers", response_model=list[SessionAnswerRead])
def list_session_answers(
    session_id: int,
    user_id: int | None = Query(default=None, ge=1),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[SessionAnswerRead]:
    if user_id is not None and user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    target_user_id = user_id or current_user_id
    answers = learning_session_repository.list_answers_by_session(
        db,
        session_id=session_id,
        user_id=target_user_id,
    )
    if answers is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return answers


@router.get("/sessions/me/{session_id}/answers", response_model=list[SessionAnswerRead])
def list_my_session_answers(
    session_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[SessionAnswerRead]:
    answers = learning_session_repository.list_answers_by_session(
        db,
        session_id=session_id,
        user_id=current_user_id,
    )
    if answers is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return answers


@router.post("/sessions/submit", response_model=SessionSubmitResponse)
async def submit_session(
    payload: SessionSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SessionSubmitResponse:
    target_user_id = application_access.resolve_target_user_id(
        requested_user_id=payload.user_id,
        current_user_id=current_user_id,
    )
    user = users_public_api.get_or_404(db=db, user_id=target_user_id)
    result = await learning_session_submission_service.submit(
        db=db,
        user_id=target_user_id,
        user_cefr_level=user.cefr_level,
        answers=payload.answers,
    )
    return SessionSubmitResponse(
        session=result.session,
        incorrect_feedback=[
            {"exercise_id": item.exercise_id, "explanation_ru": item.explanation_ru}
            for item in result.incorrect_feedback
        ],
        advice_feedback=[
            {"exercise_id": item.exercise_id, "explanation_ru": item.explanation_ru}
            for item in result.advice_feedback
        ],
    )



def _to_review_queue_item_response(item: ReviewQueueItemDTO):
    from app.modules.learning.schemas.review_schemas import ReviewQueueItem

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
    from app.modules.learning.schemas.review_schemas import ReviewSessionItem

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
    return ProgressSnapshot(
        user_id=result.user_id,
        total_sessions=result.total_sessions,
        avg_accuracy=result.avg_accuracy,
    )


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
    return ReviewSummary(
        user_id=result.user_id,
        total_tracked=result.total_tracked,
        due_now=result.due_now,
        mastered=result.mastered,
        troubled=result.troubled,
    )
