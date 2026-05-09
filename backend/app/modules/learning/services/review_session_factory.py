from __future__ import annotations

import secrets

from app.modules.learning.assemblers import to_review_session_start_dto
from app.modules.learning.contracts import ReviewSessionStartDTO
from app.modules.learning.repositories.review_repository import context_repository
from app.modules.learning.services.review_projection_service import review_projection_service
from app.modules.vocabulary.service.items import list_user_items


class ReviewSessionFactory:
    def build_srs_review_session(
        self,
        *,
        db,
        user_id: int,
        size: int,
        dedupe_keep_order,
        is_valid_word,
    ) -> ReviewSessionStartDTO:
        due_rows = context_repository.list_due_word_progress(db, user_id=user_id, limit=size * 5)
        words = dedupe_keep_order([row.word for row in due_rows if is_valid_word(row.word)])[:size]
        row_map = {row.word: row for row in due_rows}
        items = review_projection_service.build_review_session_items(
            db=db,
            user_id=user_id,
            words=words,
            progress_map=row_map,
        )
        return to_review_session_start_dto(
            user_id=user_id,
            mode="srs",
            total_items=len(items),
            items=items,
        )

    def build_random_review_session(
        self,
        *,
        db,
        user_id: int,
        size: int,
        dedupe_keep_order,
        is_valid_word,
    ) -> ReviewSessionStartDTO:
        vocabulary_items = list_user_items(db=db, user_id=user_id)
        unique_words = dedupe_keep_order(
            [item.english_lemma for item in vocabulary_items if is_valid_word(item.english_lemma)]
        )
        if not unique_words:
            return to_review_session_start_dto(user_id=user_id, mode="random", total_items=0, items=[])

        sample_size = min(size, len(unique_words))
        random_words = secrets.SystemRandom().sample(unique_words, k=sample_size)
        progress_map = context_repository.get_word_progress_map(db, user_id=user_id, words=random_words)
        items = review_projection_service.build_review_session_items(
            db=db,
            user_id=user_id,
            words=random_words,
            progress_map=progress_map,
        )
        return to_review_session_start_dto(
            user_id=user_id,
            mode="random",
            total_items=len(items),
            items=items,
        )


review_session_factory = ReviewSessionFactory()
