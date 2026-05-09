from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.review.models import matches_review_status_filter
from app.modules.review.repository import review_repository
from app.modules.training.repository import list_recent_incorrect_words

_WORD_RE = re.compile(r"^[a-z][a-z'-]{0,48}$")


def _is_valid_review_word(value: str | None) -> bool:
    if not value:
        return False
    return bool(_WORD_RE.fullmatch(value.strip().lower()))


@dataclass
class RecommendationScoreSnapshot:
    scores: dict[str, float]
    recent_error_words_stream: list[str]
    due_progress_map: dict

    def ranked_words(self, limit: int) -> list[str]:
        return [key for key, _ in sorted(self.scores.items(), key=lambda item: item[1], reverse=True)[:limit]]


class RecommendationScoringService:
    def build_snapshot(
        self,
        *,
        db: Session,
        user_id: int,
        limit: int,
    ) -> RecommendationScoreSnapshot:
        recent_error_words_stream = list_recent_incorrect_words(
            db,
            user_id=user_id,
            limit=limit * 5,
            unique=False,
        )
        candidate_rows = review_repository.list_word_progress(
            db,
            user_id=user_id,
            limit=max(limit * 3, 10),
            offset=0,
            q=None,
            sort_by="error_count",
            sort_order="desc",
        )
        troubled_rows = [
            row for row in candidate_rows
            if matches_review_status_filter(
                status_filter="troubled",
                error_count=row.error_count,
                correct_streak=row.correct_streak,
                next_review_at=row.next_review_at,
                min_streak=3,
                min_errors=2,
            )
        ]

        scores: dict[str, float] = {}
        for idx, word in enumerate(recent_error_words_stream):
            if not _is_valid_review_word(word):
                continue
            scores[word] = scores.get(word, 0.0) + (1.0 / (idx + 1))

        for row in troubled_rows:
            word = row.word.strip().lower()
            if not _is_valid_review_word(word):
                continue
            scores[word] = scores.get(word, 0.0) + 0.75

        due_progress_map = review_repository.get_word_progress_map(
            db,
            user_id=user_id,
            words=list(scores.keys()),
        )
        now = datetime.utcnow()
        for word, progress in due_progress_map.items():
            if progress.next_review_at <= now:
                scores[word] = scores.get(word, 0.0) + 1.25

        return RecommendationScoreSnapshot(
            scores=scores,
            recent_error_words_stream=recent_error_words_stream,
            due_progress_map=due_progress_map,
        )


recommendation_scoring_service = RecommendationScoringService()
