from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.modules.identity.deps import get_current_user_id
from app.modules.review.models import build_review_status
from app.modules.review.schemas import (
    ProgressSnapshot,
    ReviewPlanResponse,
    ReviewQueueBulkSubmitRequest,
    ReviewQueueBulkSubmitResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
    ReviewQueueSubmitRequest,
    ReviewSessionStartRequest,
    ReviewSessionStartResponse,
    ReviewSummary,
    WordProgressDeleteResponse,
    WordProgressListResponse,
    WordProgressRead,
)
from app.modules.review.service.srs import SRSService, get_srs_service
from app.modules.vocabulary.service.items import VocabularyService

router = APIRouter(tags=["review"])


class UserContextRead(BaseModel):
    user_id: int
    cefr_level: str | None = None
    goals: list[str] = []
    difficult_words: list[str] = []


class UserContextUpdate(BaseModel):
    cefr_level: str | None = None
    goals: list[str] = []
    difficult_words: list[str] = []


class RecommendationsResponse(BaseModel):
    user_id: int
    words: list[str] = []
    recent_error_words: list[str] = []
    difficult_words: list[str] = []
    scores: dict[str, float] = {}
    next_review_at: dict[str, Any] = {}


@router.get("/context/me/review-queue", response_model=ReviewQueueResponse)
def get_review_queue_me(
    limit: int = Query(default=20, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> ReviewQueueResponse:
    result = service.get_review_queue(user_id=current_user_id, current_user_id=current_user_id, limit=limit)
    return ReviewQueueResponse(
        user_id=result["user_id"],
        total_due=result["total_due"],
        items=[ReviewQueueItem(**item) for item in result["items"]],
    )


@router.post("/context/me/review-queue/submit", response_model=WordProgressRead)
def submit_review_queue_item_me(
    payload: ReviewQueueSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    srs_service: SRSService = Depends(get_srs_service),
    vocab_service: VocabularyService = Depends(),
) -> WordProgressRead:
    progress = srs_service.submit_review_queue_item(user_id=current_user_id, current_user_id=current_user_id, payload=payload)
    translation_map = vocab_service.get_translation_map_for_user(user_id=current_user_id, english_lemmas=[progress.word])
    return WordProgressRead(
        user_id=progress.user_id,
        word=progress.word,
        russian_translation=translation_map.get(progress.word),
        error_count=progress.error_count,
        correct_streak=progress.correct_streak,
        next_review_at=progress.next_review_at,
        status=build_review_status(
            error_count=progress.error_count,
            correct_streak=progress.correct_streak,
            next_review_at=progress.next_review_at,
        ).status,
    )


@router.post("/context/me/review-queue/submit-bulk", response_model=ReviewQueueBulkSubmitResponse)
def submit_review_queue_bulk_me(
    payload: ReviewQueueBulkSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    srs_service: SRSService = Depends(get_srs_service),
    vocab_service: VocabularyService = Depends(),
) -> ReviewQueueBulkSubmitResponse:
    result = srs_service.submit_review_queue_bulk(user_id=current_user_id, current_user_id=current_user_id, payload=payload)
    rows = result["updated"]
    words = [r.word for r in rows]
    translation_map = vocab_service.get_translation_map_for_user(user_id=current_user_id, english_lemmas=words)
    updated = [
        WordProgressRead(
            user_id=r.user_id,
            word=r.word,
            russian_translation=translation_map.get(r.word),
            error_count=r.error_count,
            correct_streak=r.correct_streak,
            next_review_at=r.next_review_at,
            status=build_review_status(error_count=r.error_count, correct_streak=r.correct_streak, next_review_at=r.next_review_at).status,
        )
        for r in rows
    ]
    return ReviewQueueBulkSubmitResponse(user_id=result["user_id"], updated=updated)


@router.post("/context/me/review-session/start", response_model=ReviewSessionStartResponse)
def start_review_session_me(
    payload: ReviewSessionStartRequest,
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> ReviewSessionStartResponse:
    from app.modules.review.schemas import ReviewSessionItem
    result = service.start_review_session(user_id=current_user_id, current_user_id=current_user_id, payload=payload)
    return ReviewSessionStartResponse(
        user_id=result["user_id"],
        mode=result["mode"],
        total_items=result["total_items"],
        items=[ReviewSessionItem(**item) for item in result["items"]],
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
    service: SRSService = Depends(get_srs_service),
) -> WordProgressListResponse:
    result = service.list_word_progress(
        user_id=current_user_id, current_user_id=current_user_id,
        limit=limit, offset=offset, status=status, q=q,
        sort_by=sort_by, sort_order=sort_order, min_streak=min_streak, min_errors=min_errors,
    )
    return WordProgressListResponse(
        user_id=result["user_id"],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        items=[WordProgressRead(**item) for item in result["items"]],
    )


@router.get("/context/me/word-progress/{word}", response_model=WordProgressRead)
def get_word_progress_me(
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    srs_service: SRSService = Depends(get_srs_service),
    vocab_service: VocabularyService = Depends(),
) -> WordProgressRead:
    progress = srs_service.get_word_progress(user_id=current_user_id, current_user_id=current_user_id, word=word)
    translation_map = vocab_service.get_translation_map_for_user(user_id=current_user_id, english_lemmas=[progress.word])
    return WordProgressRead(
        user_id=progress.user_id,
        word=progress.word,
        russian_translation=translation_map.get(progress.word),
        error_count=progress.error_count,
        correct_streak=progress.correct_streak,
        next_review_at=progress.next_review_at,
        status=build_review_status(error_count=progress.error_count, correct_streak=progress.correct_streak, next_review_at=progress.next_review_at).status,
    )


@router.delete("/context/me/word-progress/{word}", response_model=WordProgressDeleteResponse)
def delete_word_progress_me(
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> WordProgressDeleteResponse:
    result = service.delete_word_progress(user_id=current_user_id, current_user_id=current_user_id, word=word)
    return WordProgressDeleteResponse(**result)


@router.get("/context/me/review-plan", response_model=ReviewPlanResponse)
def get_review_plan_me(
    limit: int = Query(default=10, ge=1, le=100),
    horizon_hours: int = Query(default=24, ge=1, le=168),
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> ReviewPlanResponse:
    result = service.get_review_plan(
        user_id=current_user_id, current_user_id=current_user_id,
        limit=limit, horizon_hours=horizon_hours,
    )
    return ReviewPlanResponse(
        user_id=result["user_id"],
        due_count=result["due_count"],
        upcoming_count=result["upcoming_count"],
        due_now=[ReviewQueueItem(**item) for item in result["due_now"]],
        upcoming=[ReviewQueueItem(**item) for item in result["upcoming"]],
        recommended_words=result["recommended_words"],
    )


@router.get("/context/me/progress", response_model=ProgressSnapshot)
def progress_me(
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> ProgressSnapshot:
    result = service.get_progress_snapshot(user_id=None, current_user_id=current_user_id)
    return ProgressSnapshot(**result)


@router.get("/context/me/review-summary", response_model=ReviewSummary)
def review_summary_me(
    min_streak: int = Query(default=3, ge=1, le=50),
    min_errors: int = Query(default=3, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> ReviewSummary:
    result = service.get_review_summary(
        user_id=current_user_id, current_user_id=current_user_id,
        min_streak=min_streak, min_errors=min_errors,
    )
    return ReviewSummary(**result)


@router.get("/context/review-summary", response_model=ReviewSummary)
def review_summary(
    user_id: int | None = Query(default=None, ge=1),
    min_streak: int = Query(default=3, ge=1, le=50),
    min_errors: int = Query(default=3, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> ReviewSummary:
    target_user_id = user_id or current_user_id
    result = service.get_review_summary(
        user_id=target_user_id, current_user_id=current_user_id,
        min_streak=min_streak, min_errors=min_errors,
    )
    return ReviewSummary(**result)


@router.get("/context/progress", response_model=ProgressSnapshot)
def progress(
    user_id: int | None = Query(default=None, ge=1),
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> ProgressSnapshot:
    result = service.get_progress_snapshot(user_id=user_id, current_user_id=current_user_id)
    return ProgressSnapshot(**result)


@router.get("/context/{user_id}", response_model=UserContextRead)
def get_user_context(
    user_id: int,
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> UserContextRead:
    result = service.get_user_context(user_id=user_id, current_user_id=current_user_id)
    return UserContextRead(**result)


@router.put("/context/{user_id}", response_model=UserContextRead)
def update_user_context(
    user_id: int,
    _payload: UserContextUpdate,
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> UserContextRead:
    result = service.get_user_context(user_id=user_id, current_user_id=current_user_id)
    return UserContextRead(**result)


@router.get("/context/{user_id}/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    user_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> RecommendationsResponse:
    result = service.get_recommendations(user_id=user_id, current_user_id=current_user_id, limit=limit)
    return RecommendationsResponse(**result)


@router.get("/context/{user_id}/review-queue", response_model=ReviewQueueResponse)
def get_review_queue(
    user_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> ReviewQueueResponse:
    result = service.get_review_queue(user_id=user_id, current_user_id=current_user_id, limit=limit)
    return ReviewQueueResponse(
        user_id=result["user_id"],
        total_due=result["total_due"],
        items=[ReviewQueueItem(**item) for item in result["items"]],
    )


@router.post("/context/{user_id}/review-queue/submit", response_model=WordProgressRead)
def submit_review_queue_item(
    user_id: int,
    payload: ReviewQueueSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    srs_service: SRSService = Depends(get_srs_service),
    vocab_service: VocabularyService = Depends(),
) -> WordProgressRead:
    progress = srs_service.submit_review_queue_item(user_id=user_id, current_user_id=current_user_id, payload=payload)
    translation_map = vocab_service.get_translation_map_for_user(user_id=user_id, english_lemmas=[progress.word])
    return WordProgressRead(
        user_id=progress.user_id,
        word=progress.word,
        russian_translation=translation_map.get(progress.word),
        error_count=progress.error_count,
        correct_streak=progress.correct_streak,
        next_review_at=progress.next_review_at,
        status=build_review_status(
            error_count=progress.error_count,
            correct_streak=progress.correct_streak,
            next_review_at=progress.next_review_at,
        ).status,
    )


@router.post("/context/{user_id}/review-queue/submit-bulk", response_model=ReviewQueueBulkSubmitResponse)
def submit_review_queue_bulk(
    user_id: int,
    payload: ReviewQueueBulkSubmitRequest,
    current_user_id: int = Depends(get_current_user_id),
    srs_service: SRSService = Depends(get_srs_service),
    vocab_service: VocabularyService = Depends(),
) -> ReviewQueueBulkSubmitResponse:
    result = srs_service.submit_review_queue_bulk(user_id=user_id, current_user_id=current_user_id, payload=payload)
    rows = result["updated"]
    words = [r.word for r in rows]
    translation_map = vocab_service.get_translation_map_for_user(user_id=user_id, english_lemmas=words)
    updated = [
        WordProgressRead(
            user_id=r.user_id,
            word=r.word,
            russian_translation=translation_map.get(r.word),
            error_count=r.error_count,
            correct_streak=r.correct_streak,
            next_review_at=r.next_review_at,
            status=build_review_status(error_count=r.error_count, correct_streak=r.correct_streak, next_review_at=r.next_review_at).status,
        )
        for r in rows
    ]
    return ReviewQueueBulkSubmitResponse(user_id=result["user_id"], updated=updated)


@router.get("/context/{user_id}/word-progress", response_model=WordProgressListResponse)
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
    service: SRSService = Depends(get_srs_service),
) -> WordProgressListResponse:
    result = service.list_word_progress(
        user_id=user_id, current_user_id=current_user_id,
        limit=limit, offset=offset, status=status, q=q,
        sort_by=sort_by, sort_order=sort_order, min_streak=min_streak, min_errors=min_errors,
    )
    return WordProgressListResponse(
        user_id=result["user_id"],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        items=[WordProgressRead(**item) for item in result["items"]],
    )


@router.get("/context/{user_id}/word-progress/{word}", response_model=WordProgressRead)
def get_word_progress(
    user_id: int,
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    srs_service: SRSService = Depends(get_srs_service),
    vocab_service: VocabularyService = Depends(),
) -> WordProgressRead:
    progress = srs_service.get_word_progress(user_id=user_id, current_user_id=current_user_id, word=word)
    translation_map = vocab_service.get_translation_map_for_user(user_id=user_id, english_lemmas=[progress.word])
    return WordProgressRead(
        user_id=progress.user_id,
        word=progress.word,
        russian_translation=translation_map.get(progress.word),
        error_count=progress.error_count,
        correct_streak=progress.correct_streak,
        next_review_at=progress.next_review_at,
        status=build_review_status(error_count=progress.error_count, correct_streak=progress.correct_streak, next_review_at=progress.next_review_at).status,
    )


@router.delete("/context/{user_id}/word-progress/{word}", response_model=WordProgressDeleteResponse)
def delete_word_progress(
    user_id: int,
    word: str,
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> WordProgressDeleteResponse:
    result = service.delete_word_progress(user_id=user_id, current_user_id=current_user_id, word=word)
    return WordProgressDeleteResponse(**result)


@router.get("/context/{user_id}/review-plan", response_model=ReviewPlanResponse)
def get_review_plan(
    user_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    horizon_hours: int = Query(default=24, ge=1, le=168),
    current_user_id: int = Depends(get_current_user_id),
    service: SRSService = Depends(get_srs_service),
) -> ReviewPlanResponse:
    result = service.get_review_plan(
        user_id=user_id, current_user_id=current_user_id,
        limit=limit, horizon_hours=horizon_hours,
    )
    return ReviewPlanResponse(
        user_id=result["user_id"],
        due_count=result["due_count"],
        upcoming_count=result["upcoming_count"],
        due_now=[ReviewQueueItem(**item) for item in result["due_now"]],
        upcoming=[ReviewQueueItem(**item) for item in result["upcoming"]],
        recommended_words=result["recommended_words"],
    )
