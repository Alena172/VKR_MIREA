from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReviewQueueItem(BaseModel):
    word: str
    russian_translation: str | None = None
    next_review_at: datetime
    error_count: int
    correct_streak: int
    status: Literal["due", "upcoming", "mastered", "troubled"]


class ReviewQueueResponse(BaseModel):
    user_id: int
    total_due: int
    items: list[ReviewQueueItem]


class ReviewQueueSubmitRequest(BaseModel):
    word: str = Field(min_length=1, max_length=200)
    vocabulary_id: int | None = None
    is_correct: bool


class ReviewQueueBulkSubmitItem(BaseModel):
    word: str = Field(min_length=1, max_length=200)
    vocabulary_id: int | None = None
    is_correct: bool


class ReviewQueueBulkSubmitRequest(BaseModel):
    items: list[ReviewQueueBulkSubmitItem] = Field(default_factory=list, max_length=200)


class WordProgressRead(BaseModel):
    user_id: int
    word: str
    russian_translation: str | None = None
    error_count: int
    correct_streak: int
    next_review_at: datetime
    status: Literal["due", "upcoming", "mastered", "troubled"]


class WordProgressListResponse(BaseModel):
    user_id: int
    total: int
    limit: int
    offset: int
    items: list[WordProgressRead]


class ReviewQueueBulkSubmitResponse(BaseModel):
    user_id: int
    updated: list[WordProgressRead]


class ReviewPlanResponse(BaseModel):
    user_id: int
    due_count: int
    upcoming_count: int
    due_now: list[ReviewQueueItem]
    upcoming: list[ReviewQueueItem]
    recommended_words: list[str]


class ReviewSessionStartRequest(BaseModel):
    mode: Literal["srs", "random"] = "srs"
    size: int = Field(default=20, ge=1, le=200)


class ReviewSessionItem(BaseModel):
    word: str
    vocabulary_id: int | None = None
    russian_translation: str | None = None
    context_definition: str | None = None
    source_sentence: str | None = None
    next_review_at: datetime | None = None
    error_count: int = 0
    correct_streak: int = 0
    status: Literal["due", "upcoming", "mastered", "troubled"]


class ReviewSessionStartResponse(BaseModel):
    user_id: int
    mode: Literal["srs", "random"]
    total_items: int
    items: list[ReviewSessionItem]


class WordProgressDeleteResponse(BaseModel):
    user_id: int
    word: str
    progress_deleted: bool
    removed_from_difficult_words: bool = False


class ProgressSnapshot(BaseModel):
    user_id: int | None = None
    total_sessions: int
    avg_accuracy: float


class ReviewSummary(BaseModel):
    user_id: int
    total_tracked: int
    due_now: int
    mastered: int
    troubled: int
