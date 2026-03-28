from __future__ import annotations

from app.modules.learning_session.assembler import to_learning_progress_dto
from app.modules.learning_session.contracts import LearningProgressDTO
from app.modules.learning_session.repository import learning_session_repository

__all__ = [
    "LearningProgressDTO",
    "learning_session_public_api",
]


class LearningSessionPublicApi:
    list_recent_incorrect_words = staticmethod(learning_session_repository.list_recent_incorrect_words)

    @staticmethod
    def get_progress_dto(db, *, user_id: int) -> LearningProgressDTO:
        total_sessions, average_accuracy = learning_session_repository.get_progress_snapshot(
            db,
            user_id=user_id,
        )
        return to_learning_progress_dto(
            total_sessions=total_sessions,
            average_accuracy=average_accuracy,
        )


learning_session_public_api = LearningSessionPublicApi()
