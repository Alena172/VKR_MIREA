from __future__ import annotations

from app.modules.learning_session.repository import learning_session_repository

__all__ = [
    "learning_session_public_api",
]


class LearningSessionPublicApi:
    list_recent_incorrect_words = staticmethod(learning_session_repository.list_recent_incorrect_words)


learning_session_public_api = LearningSessionPublicApi()
