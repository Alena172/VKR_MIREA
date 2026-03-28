from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearningProgressDTO:
    total_sessions: int
    average_accuracy: float
