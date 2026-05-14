from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExerciseGenerateRequest(BaseModel):
    """Запрос генерации упражнений для служебного endpoint."""

    user_id: int | None = Field(default=None, ge=1)
    vocabulary_ids: list[int] = Field(default_factory=list)
    size: int = Field(default=10, ge=1, le=30)
    fast_start: bool = False
    incremental: bool = False
    mode: str = Field(
        default="sentence_translation_full",
        pattern="^(sentence_translation_full|word_definition_match|word_scramble)$",
    )


class ExerciseGenerateRequestMe(BaseModel):
    """Запрос генерации упражнений для текущего пользователя."""

    vocabulary_ids: list[int] = Field(default_factory=list)
    size: int = Field(default=10, ge=1, le=30)
    fast_start: bool = False
    incremental: bool = False
    mode: str = Field(
        default="sentence_translation_full",
        pattern="^(sentence_translation_full|word_definition_match|word_scramble)$",
    )


class ExerciseItem(BaseModel):
    """Упражнение, которое frontend показывает пользователю."""

    prompt: str
    answer: str
    exercise_type: str
    target_word: str | None = None
    options: list[str] = Field(default_factory=list)


class ExerciseGenerateResponse(BaseModel):
    """Ответ синхронной генерации упражнений."""

    exercises: list[ExerciseItem]
    note: str


class SessionAnswer(BaseModel):
    exercise_id: int = Field(ge=1)
    exercise_type: str | None = Field(default=None, max_length=64)
    target_word: str | None = Field(default=None, max_length=200)
    vocabulary_id: int | None = Field(default=None, ge=1)
    prompt: str | None = Field(default=None, max_length=2000)
    expected_answer: str | None = Field(default=None, max_length=1000)
    user_answer: str = Field(min_length=1, max_length=1000)
    is_correct: bool | None = None


class SessionSubmitRequest(BaseModel):
    user_id: int | None = Field(default=None, ge=1)
    answers: list[SessionAnswer] = Field(default_factory=list)


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    total: int
    correct: int
    accuracy: float
    created_at: datetime


class SessionHistoryResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[SessionSummary]


class SessionAnswerFeedback(BaseModel):
    exercise_id: int
    explanation_ru: str


class SessionSubmitResponse(BaseModel):
    session: SessionSummary
    incorrect_feedback: list[SessionAnswerFeedback] = Field(default_factory=list)
    advice_feedback: list[SessionAnswerFeedback] = Field(default_factory=list)


class SessionAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    exercise_id: int
    exercise_type: str | None = None
    target_word: str | None = None
    prompt: str | None = None
    expected_answer: str | None = None
    user_answer: str
    is_correct: bool
    explanation_ru: str | None = None


@dataclass(frozen=True)
class ExerciseDTO:
    """Одно упражнение, готовое для показа пользователю."""

    prompt: str
    answer: str
    exercise_type: str
    target_word: str | None
    options: list[str]


@dataclass(frozen=True)
class ExerciseGenerateResultDTO:
    """Результат генерации набора упражнений."""

    exercises: list[ExerciseDTO]
    note: str


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


@dataclass(frozen=True)
class LearningProgressDTO:
    """Общая учебная статистика пользователя."""

    total_sessions: int
    average_accuracy: float
