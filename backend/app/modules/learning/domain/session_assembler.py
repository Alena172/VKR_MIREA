from __future__ import annotations

from app.modules.learning.domain.session_contracts import LearningProgressDTO


def to_learning_progress_dto(*, total_sessions: int, average_accuracy: float) -> LearningProgressDTO:
    return LearningProgressDTO(
        total_sessions=total_sessions,
        average_accuracy=average_accuracy,
    )
