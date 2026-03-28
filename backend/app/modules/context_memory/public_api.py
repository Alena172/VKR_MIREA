from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.context_memory.contracts import WordProgressUpdate
from app.modules.context_memory.repository import context_repository

__all__ = [
    "WordProgressUpdate",
    "context_memory_public_api",
]


class ContextMemoryPublicApi:
    @staticmethod
    def get_effective_cefr_level(*, db: Session, user_id: int, fallback_cefr: str) -> str:
        from app.modules.context_memory.application_service import context_memory_application_service

        return context_memory_application_service.get_effective_cefr_level(
            db=db,
            user_id=user_id,
            fallback_cefr=fallback_cefr,
        )

    @staticmethod
    def ensure_word_progress_entry(*, db: Session, user_id: int, word: str) -> bool:
        from app.modules.context_memory.application_service import context_memory_application_service

        return context_memory_application_service.ensure_word_progress_entry(
            db=db,
            user_id=user_id,
            word=word,
        )

    @staticmethod
    def update_learning_progress(
        *,
        db: Session,
        user_id: int,
        user_cefr_level: str | None,
        updates: list[WordProgressUpdate],
    ) -> list[str]:
        from app.modules.context_memory.application_service import context_memory_application_service

        return context_memory_application_service.update_learning_progress(
            db=db,
            user_id=user_id,
            user_cefr_level=user_cefr_level,
            updates=updates,
        )

    @staticmethod
    def list_mastered_lemmas(
        *,
        db: Session,
        user_id: int,
        min_streak: int = 2,
        max_errors: int = 1,
    ) -> set[str]:
        rows = context_repository.list_word_progress(
            db,
            user_id=user_id,
            limit=10000,
            offset=0,
            status="all",
            q=None,
            sort_by="correct_streak",
            sort_order="desc",
            min_streak=min_streak,
            min_errors=max_errors,
        )
        return {
            row.word.strip().lower()
            for row in rows
            if row.word and row.correct_streak >= min_streak and row.error_count <= max_errors
        }


context_memory_public_api = ContextMemoryPublicApi()
