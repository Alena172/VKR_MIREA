"""HTTP-модели review-модуля для SRS и очереди повторения."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReviewQueueItem(BaseModel):
    """Один элемент очереди повторения."""

    word: str
    russian_translation: str | None = None
    next_review_at: datetime
    error_count: int
    correct_streak: int
    status: Literal["due", "upcoming", "mastered", "troubled"]


class ReviewQueueResponse(BaseModel):
    """Список слов, которые нужно или скоро нужно повторить."""

    user_id: int
    total_due: int
    items: list[ReviewQueueItem]


class ReviewQueueSubmitRequest(BaseModel):
    """Ответ пользователя по одному слову из review queue."""

    word: str = Field(min_length=1, max_length=200)
    vocabulary_id: int | None = None
    is_correct: bool


class ReviewQueueBulkSubmitItem(BaseModel):
    """Один элемент в пачке результатов повторения."""

    word: str = Field(min_length=1, max_length=200)
    vocabulary_id: int | None = None
    is_correct: bool


class ReviewQueueBulkSubmitRequest(BaseModel):
    """Пакет результатов повторения для массового обновления прогресса."""

    items: list[ReviewQueueBulkSubmitItem] = Field(default_factory=list, max_length=200)


class WordProgressRead(BaseModel):
    """Состояние запоминания слова в SRS-системе."""

    user_id: int
    word: str
    vocabulary_id: int | None = None
    russian_translation: str | None = None
    error_count: int
    correct_streak: int
    next_review_at: datetime
    status: Literal["due", "upcoming", "mastered", "troubled"]


class WordProgressListResponse(BaseModel):
    """Пагинированный список SRS-прогресса по словам."""

    user_id: int
    total: int
    limit: int
    offset: int
    items: list[WordProgressRead]


class ReviewQueueBulkSubmitResponse(BaseModel):
    """Ответ после массового сохранения результатов повторения."""

    user_id: int
    updated: list[WordProgressRead]


class ReviewPlanResponse(BaseModel):
    """Короткий план: что повторять сейчас и что скоро станет актуальным."""

    user_id: int
    due_count: int
    upcoming_count: int
    due_now: list[ReviewQueueItem]
    upcoming: list[ReviewQueueItem]
    recommended_words: list[str]


class ReviewSessionStartRequest(BaseModel):
    """Параметры запуска отдельной review-сессии."""

    mode: Literal["srs", "random", "troubled"] = "srs"
    size: int = Field(default=20, ge=1, le=200)


class ReviewSessionItem(BaseModel):
    """Слово, включённое в review-сессию."""

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
    """Подготовленная review-сессия для клиента."""

    user_id: int
    mode: Literal["srs", "random", "troubled"]
    total_items: int
    items: list[ReviewSessionItem]


class WordProgressDeleteResponse(BaseModel):
    """Результат удаления SRS-прогресса по конкретному слову."""

    user_id: int
    vocabulary_id: int | None = None
    progress_deleted: bool
    removed_from_difficult_words: bool = False


class ProgressSnapshot(BaseModel):
    """Сводные метрики обучения пользователя."""

    user_id: int | None = None
    total_sessions: int
    avg_accuracy: float


class ReviewSummary(BaseModel):
    """Агрегированная сводка по состоянию слов в системе повторения."""

    user_id: int
    total_tracked: int
    due_now: int
    mastered: int
    troubled: int
