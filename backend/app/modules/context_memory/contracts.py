from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class WordProgressUpdate:
    word: str
    is_correct: bool
    mark_difficult: bool = False


@dataclass(frozen=True)
class EffectiveCefrDTO:
    cefr_level: str


@dataclass(frozen=True)
class WordProgressTrackingDTO:
    word: str
    tracked: bool


@dataclass(frozen=True)
class LearningProgressUpdateResultDTO:
    difficult_words_added: list[str]


@dataclass(frozen=True)
class MasteredLemmaDTO:
    word: str


@dataclass(frozen=True)
class ProgressSnapshotDTO:
    user_id: int
    total_sessions: int
    avg_accuracy: float


@dataclass(frozen=True)
class ReviewSummaryDTO:
    user_id: int
    total_tracked: int
    due_now: int
    mastered: int
    troubled: int


@dataclass(frozen=True)
class ContextRecommendationsDTO:
    user_id: int
    words: list[str]
    recent_error_words: list[str]
    difficult_words: list[str]
    scores: dict[str, float]
    next_review_at: dict[str, datetime | None]


@dataclass(frozen=True)
class ReviewQueueItemDTO:
    word: str
    russian_translation: str | None
    next_review_at: datetime
    error_count: int
    correct_streak: int


@dataclass(frozen=True)
class ReviewQueueResponseDTO:
    user_id: int
    total_due: int
    items: list[ReviewQueueItemDTO]


@dataclass(frozen=True)
class WordProgressDTO:
    user_id: int
    word: str
    russian_translation: str | None
    error_count: int
    correct_streak: int
    next_review_at: datetime


@dataclass(frozen=True)
class WordProgressListDTO:
    user_id: int
    total: int
    limit: int
    offset: int
    items: list[WordProgressDTO]


@dataclass(frozen=True)
class ReviewQueueBulkSubmitDTO:
    user_id: int
    updated: list[WordProgressDTO]


@dataclass(frozen=True)
class ReviewSessionItemDTO:
    word: str
    russian_translation: str | None
    context_definition: str | None
    next_review_at: datetime | None
    error_count: int
    correct_streak: int


@dataclass(frozen=True)
class ReviewSessionStartDTO:
    user_id: int
    mode: str
    total_items: int
    items: list[ReviewSessionItemDTO]


@dataclass(frozen=True)
class WordProgressDeleteDTO:
    user_id: int
    word: str
    progress_deleted: bool
    removed_from_difficult_words: bool


@dataclass(frozen=True)
class ReviewPlanDTO:
    user_id: int
    due_count: int
    upcoming_count: int
    due_now: list[ReviewQueueItemDTO]
    upcoming: list[ReviewQueueItemDTO]
    recommended_words: list[str]


@dataclass(frozen=True)
class ContextGarbageCleanupDTO:
    user_id: int
    removed_word_progress: int
    removed_difficult_words: int
