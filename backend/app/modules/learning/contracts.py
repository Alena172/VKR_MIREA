from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.modules.learning.models.review_status import ReviewStatus


@dataclass(frozen=True)
class ExerciseItemDTO:
    """Одно упражнение, готовое для показа пользователю."""

    prompt: str
    answer: str
    exercise_type: str
    target_word: str | None
    options: list[str]


@dataclass(frozen=True)
class ExerciseGenerateResultDTO:
    """Результат генерации набора упражнений."""

    exercises: list[ExerciseItemDTO]
    note: str


@dataclass(frozen=True)
class WordProgressUpdate:
    """Минимальное событие обновления прогресса по слову."""

    word: str
    is_correct: bool


@dataclass(frozen=True)
class WordProgressTrackingDTO:
    """Показывает, отслеживается ли слово в SRS-прогрессе."""

    word: str
    tracked: bool


@dataclass(frozen=True)
class LearningProgressUpdateResultDTO:
    """Список слов, прогресс которых был обновлен."""

    updated_words: list[str]


@dataclass(frozen=True)
class MasteredLemmaDTO:
    """Слово, которое считается освоенным."""

    word: str


@dataclass(frozen=True)
class ProgressSnapshotDTO:
    """Краткая статистика учебных сессий пользователя."""

    user_id: int
    total_sessions: int
    avg_accuracy: float


@dataclass(frozen=True)
class ReviewSummaryDTO:
    """Агрегированная сводка по повторению слов."""

    user_id: int
    total_tracked: int
    due_now: int
    mastered: int
    troubled: int


@dataclass(frozen=True)
class ReviewQueueItemDTO:
    """Один элемент очереди повторения."""

    word: str
    russian_translation: str | None
    next_review_at: datetime
    error_count: int
    correct_streak: int
    status: ReviewStatus


@dataclass(frozen=True)
class ReviewQueueResponseDTO:
    """Очередь слов, которые нужно повторить сейчас."""

    user_id: int
    total_due: int
    items: list[ReviewQueueItemDTO]


@dataclass(frozen=True)
class WordProgressDTO:
    """Текущее состояние SRS-прогресса одного слова."""

    user_id: int
    word: str
    russian_translation: str | None
    error_count: int
    correct_streak: int
    next_review_at: datetime
    status: ReviewStatus


@dataclass(frozen=True)
class WordProgressListDTO:
    """Постраничный список прогресса по словам."""

    user_id: int
    total: int
    limit: int
    offset: int
    items: list[WordProgressDTO]


@dataclass(frozen=True)
class ReviewQueueBulkSubmitDTO:
    """Результат массовой отправки повторения."""

    user_id: int
    updated: list[WordProgressDTO]


@dataclass(frozen=True)
class ReviewSessionItemDTO:
    """Карточка слова внутри короткой review-сессии."""

    word: str
    russian_translation: str | None
    context_definition: str | None
    next_review_at: datetime | None
    error_count: int
    correct_streak: int
    status: ReviewStatus


@dataclass(frozen=True)
class ReviewSessionStartDTO:
    """Набор карточек для старта review-сессии."""

    user_id: int
    mode: str
    total_items: int
    items: list[ReviewSessionItemDTO]


@dataclass(frozen=True)
class WordProgressDeleteDTO:
    """Результат удаления прогресса по слову."""

    user_id: int
    word: str
    progress_deleted: bool


@dataclass(frozen=True)
class ReviewPlanDTO:
    """План повторения: что повторить сейчас и что скоро подойдет."""

    user_id: int
    due_count: int
    upcoming_count: int
    due_now: list[ReviewQueueItemDTO]
    upcoming: list[ReviewQueueItemDTO]
    recommended_words: list[str]


@dataclass(frozen=True)
class LearningProgressDTO:
    """Общая учебная статистика пользователя."""

    total_sessions: int
    average_accuracy: float


@dataclass(frozen=True)
class SessionAnswerFeedbackDTO:
    """Пояснение по конкретному ответу в учебной сессии."""

    exercise_id: int
    explanation_ru: str


@dataclass(frozen=True)
class SessionSubmitResultDTO:
    """Результат сохранения и оценки учебной сессии."""

    session: Any
    incorrect_feedback: list[SessionAnswerFeedbackDTO]
    advice_feedback: list[SessionAnswerFeedbackDTO]
