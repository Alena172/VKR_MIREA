from __future__ import annotations

from datetime import datetime

from app.modules.learning.assemblers import (
    to_review_queue_item_dto,
    to_review_session_item_dto,
    to_word_progress_dto,
)
from app.modules.learning.contracts import ReviewQueueItemDTO, ReviewSessionItemDTO, WordProgressDTO
from app.modules.learning.models.review_models import WordProgressModel
from app.modules.learning.models.review_status import build_review_status
from app.modules.vocabulary.items_public_api import vocabulary_public_api


class ReviewProjectionService:
    def build_review_queue_items(
        self,
        *,
        db,
        user_id: int,
        rows: list[WordProgressModel],
        is_valid_word,
    ) -> list[ReviewQueueItemDTO]:
        words = [row.word for row in rows]
        translation_map = vocabulary_public_api.get_translation_map(db, user_id=user_id, english_lemmas=words)
        return [
            to_review_queue_item_dto(
                word=row.word,
                russian_translation=translation_map.get(row.word),
                next_review_at=row.next_review_at,
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                status=build_review_status(
                    error_count=row.error_count,
                    correct_streak=row.correct_streak,
                    next_review_at=row.next_review_at,
                ).status,
            )
            for row in rows
            if is_valid_word(row.word)
        ]

    def to_word_progress_reads(
        self,
        *,
        db,
        user_id: int,
        progress_rows: list[WordProgressModel],
    ) -> list[WordProgressDTO]:
        words = [row.word for row in progress_rows]
        translation_map = vocabulary_public_api.get_translation_map(db, user_id=user_id, english_lemmas=words)
        return [
            to_word_progress_dto(
                user_id=row.user_id,
                word=row.word,
                russian_translation=translation_map.get(row.word),
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                status=build_review_status(
                    error_count=row.error_count,
                    correct_streak=row.correct_streak,
                    next_review_at=row.next_review_at,
                ).status,
            )
            for row in progress_rows
        ]

    def to_word_progress_read(
        self,
        *,
        db,
        user_id: int,
        progress: WordProgressModel,
    ) -> WordProgressDTO:
        translation_map = vocabulary_public_api.get_translation_map(
            db,
            user_id=user_id,
            english_lemmas=[progress.word],
        )
        return to_word_progress_dto(
            user_id=progress.user_id,
            word=progress.word,
            russian_translation=translation_map.get(progress.word),
            error_count=progress.error_count,
            correct_streak=progress.correct_streak,
            next_review_at=progress.next_review_at,
            status=build_review_status(
                error_count=progress.error_count,
                correct_streak=progress.correct_streak,
                next_review_at=progress.next_review_at,
            ).status,
        )

    def build_review_session_items(
        self,
        *,
        db,
        user_id: int,
        words: list[str],
        progress_map: dict[str, WordProgressModel],
    ) -> list[ReviewSessionItemDTO]:
        translation_map = vocabulary_public_api.get_translation_map(db, user_id=user_id, english_lemmas=words)
        definition_map = vocabulary_public_api.get_definition_map(db, user_id=user_id, english_lemmas=words)
        return [
            to_review_session_item_dto(
                word=word,
                russian_translation=translation_map.get(word),
                context_definition=definition_map.get(word),
                next_review_at=progress_map[word].next_review_at if word in progress_map else None,
                error_count=progress_map[word].error_count if word in progress_map else 0,
                correct_streak=progress_map[word].correct_streak if word in progress_map else 0,
                status=build_review_status(
                    error_count=progress_map[word].error_count if word in progress_map else 0,
                    correct_streak=progress_map[word].correct_streak if word in progress_map else 0,
                    next_review_at=progress_map[word].next_review_at if word in progress_map else datetime.utcnow(),
                ).status,
            )
            for word in words
        ]


review_projection_service = ReviewProjectionService()
