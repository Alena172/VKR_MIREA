from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExerciseItemDTO:
    prompt: str
    answer: str
    exercise_type: str
    options: list[str]


@dataclass(frozen=True)
class ExerciseGenerateResultDTO:
    exercises: list[ExerciseItemDTO]
    note: str
