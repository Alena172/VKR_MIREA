from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from fastapi import Depends

from app.modules.review.models import matches_review_status_filter
from app.modules.review.repository import ReviewRepository, _normalize_valid_word


@dataclass
class RecommendationScoreSnapshot:
    scores: dict[str, float] = field(default_factory=dict)

    def ranked_words(self, limit: int) -> list[str]:
        return [k for k, _ in sorted(self.scores.items(), key=lambda x: x[1], reverse=True)[:limit]]


class RecommendationScoringService:
    def __init__(
        self,
        review_repo: ReviewRepository = Depends(),
    ) -> None:
        self._review_repo = review_repo
        self._submission_service = None

    def set_submission_service(self, submission_service) -> None:
        self._submission_service = submission_service

    def build_snapshot(self, *, user_id: int, limit: int) -> RecommendationScoreSnapshot:
        recent_errors = (
            self._submission_service.list_recent_incorrect_words(user_id=user_id, limit=limit * 5, unique=False)
            if self._submission_service is not None
            else []
        )
        candidate_rows = self._review_repo.list_word_progress(
            user_id=user_id, limit=max(limit * 3, 10), offset=0, q=None,
            sort_by="error_count", sort_order="desc",
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
        for idx, word in enumerate(recent_errors):
            if _normalize_valid_word(word) is not None:
                scores[word] = scores.get(word, 0.0) + (1.0 / (idx + 1))

        for row in troubled_rows:
            word = row.word.strip().lower()
            if _normalize_valid_word(word) is not None:
                scores[word] = scores.get(word, 0.0) + 0.75

        now = datetime.utcnow()
        progress_map = self._review_repo.get_word_progress_map(user_id=user_id, words=list(scores.keys()))
        for word, progress in progress_map.items():
            if progress.next_review_at <= now:
                scores[word] = scores.get(word, 0.0) + 1.25

        return RecommendationScoreSnapshot(scores=scores)
