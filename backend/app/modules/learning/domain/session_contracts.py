from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LearningProgressDTO:
    total_sessions: int
    average_accuracy: float


@dataclass(frozen=True)
class SessionAnswerFeedbackDTO:
    exercise_id: int
    explanation_ru: str


@dataclass(frozen=True)
class SessionSubmitResultDTO:
    session: Any
    incorrect_feedback: list[SessionAnswerFeedbackDTO]
    advice_feedback: list[SessionAnswerFeedbackDTO]
