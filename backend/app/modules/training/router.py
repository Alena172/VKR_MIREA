from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.application import application_access
from app.modules.identity.deps import get_current_user_id
from app.modules.training.repository import TrainingRepository
from app.modules.training.schemas import (
    ExerciseGenerateRequestMe,
    ExerciseGenerateResponse,
    ExerciseItem,
    SessionAnswerRead,
    SessionHistoryResponse,
    SessionSubmitRequest,
    SessionSubmitResponse,
    SubmittedAnswerResult,
)
from app.modules.training.service.exercises import TrainingService
from app.modules.training.service.submission import SubmissionService

router = APIRouter()


@router.post("/exercises/me/generate", response_model=ExerciseGenerateResponse)
async def generate_me(
    payload: ExerciseGenerateRequestMe,
    current_user_id: int = Depends(get_current_user_id),
    service: TrainingService = Depends(),
) -> ExerciseGenerateResponse:
    result = await service.generate_for_user(
        user_id=current_user_id,
        vocabulary_ids=payload.vocabulary_ids,
        size=payload.size,
        mode=payload.mode,
        fast_start=payload.fast_start,
        incremental=payload.incremental,
    )
    return ExerciseGenerateResponse(
        exercises=[
            ExerciseItem(
                prompt=e.prompt,
                answer=e.answer,
                exercise_type=e.exercise_type,
                target_word=e.target_word,
                options=e.options,
            )
            for e in result.exercises
        ],
        note=result.note,
    )


@router.get("/sessions/me", response_model=SessionHistoryResponse)
def list_my_sessions(
    limit: int = Query(default=10, ge=1),
    offset: int = Query(default=0, ge=0),
    min_accuracy: float | None = Query(default=None, ge=0.0, le=1.0),
    max_accuracy: float | None = Query(default=None, ge=0.0, le=1.0),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    current_user_id: int = Depends(get_current_user_id),
    repo: TrainingRepository = Depends(),
) -> SessionHistoryResponse:
    if min_accuracy is not None and max_accuracy is not None and min_accuracy > max_accuracy:
        raise HTTPException(status_code=400, detail="min_accuracy cannot be greater than max_accuracy")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from cannot be after date_to")

    created_from = datetime.combine(date_from, time.min) if date_from is not None else None
    created_to = datetime.combine(date_to + timedelta(days=1), time.min) if date_to is not None else None

    items = repo.list_sessions_paginated(
        user_id=current_user_id,
        limit=limit,
        offset=offset,
        min_accuracy=min_accuracy,
        max_accuracy=max_accuracy,
        created_from=created_from,
        created_to=created_to,
    )
    total = repo.count_sessions(
        user_id=current_user_id,
        min_accuracy=min_accuracy,
        max_accuracy=max_accuracy,
        created_from=created_from,
        created_to=created_to,
    )
    return SessionHistoryResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/sessions/me/{session_id}", response_model=SessionSubmitResponse)
def get_my_session(
    session_id: int,
    current_user_id: int = Depends(get_current_user_id),
    repo: TrainingRepository = Depends(),
) -> SessionSubmitResponse:
    session_row = repo.get_session_by_id(session_id=session_id, user_id=current_user_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    answers = repo.list_answers_for_session(session_id=session_id)
    return SessionSubmitResponse(
        session=session_row,
        answers=[
            SubmittedAnswerResult(
                exercise_id=a.exercise_id,
                exercise_type=a.exercise_type,
                prompt=a.prompt,
                expected_answer=a.expected_answer,
                user_answer=a.user_answer,
                is_correct=a.is_correct,
            )
            for a in answers
        ],
        llm_pending_count=0,
    )


@router.get("/sessions/me/{session_id}/answers", response_model=list[SessionAnswerRead])
def list_my_session_answers(
    session_id: int,
    current_user_id: int = Depends(get_current_user_id),
    repo: TrainingRepository = Depends(),
) -> list[SessionAnswerRead]:
    answers = repo.list_answers_by_session(session_id=session_id, user_id=current_user_id)
    if answers is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return answers


@router.post("/sessions/submit", response_model=SessionSubmitResponse)
async def submit_session(
    payload: SessionSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    service: SubmissionService = Depends(),
) -> SessionSubmitResponse:
    target_user_id = application_access.resolve_target_user_id(
        requested_user_id=payload.user_id,
        current_user_id=current_user_id,
    )
    result = await service.submit(
        user_id=target_user_id,
        answers=payload.answers,
    )
    return SessionSubmitResponse(
        session=result.session,
        answers=[
            SubmittedAnswerResult(
                exercise_id=a.exercise_id,
                exercise_type=a.exercise_type,
                prompt=a.prompt,
                expected_answer=a.expected_answer,
                user_answer=a.user_answer,
                is_correct=a.is_correct,
            )
            for a in result.evaluated_answers
        ],
        llm_pending_count=result.llm_pending_count,
    )
