from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from sqlalchemy.orm import Session

from app.modules.learning.review.repository import context_repository
from app.modules.learning.review.review_status import matches_review_status_filter
from app.modules.learning_graph.public_api import learning_graph_public_api
from app.modules.learning.session.public_api import learning_session_public_api

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
    def _apply_learning_graph_boost(
        self,
        *,
        db: Session,
        user_id: int,
        scores: dict[str, float],
        limit: int,
    ) -> None:
        graph_items = learning_graph_public_api.list_recommendation_items(
            db=db,
            user_id=user_id,
            mode="mixed",
            limit=max(limit * 3, 10),
        )
        for rank, item in enumerate(graph_items):
            word = item.english_lemma.strip().lower()
            if not _is_valid_review_word(word):
                continue
            rank_decay = 1.0 / (rank + 1)
            graph_signal = min(6.0, max(0.0, float(item.score)))
            boost = 0.75 * rank_decay + 0.08 * graph_signal
            scores[word] = scores.get(word, 0.0) + boost

    def build_snapshot(
        self,
        *,
        db: Session,
        user_id: int,
        limit: int,
    ) -> RecommendationScoreSnapshot:
        recent_error_words_stream = learning_session_public_api.list_recent_incorrect_words(
            db,
            user_id=user_id,
            limit=limit * 5,
            unique=False,
        )
        candidate_rows = context_repository.list_word_progress(
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

        due_progress_map = context_repository.get_word_progress_map(
            db,
            user_id=user_id,
            words=list(scores.keys()),
        )
        now = datetime.utcnow()
        for word, progress in due_progress_map.items():
            if progress.next_review_at <= now:
                scores[word] = scores.get(word, 0.0) + 1.25

        self._apply_learning_graph_boost(
            db=db,
            user_id=user_id,
            scores=scores,
            limit=limit,
        )

        return RecommendationScoreSnapshot(
            scores=scores,
            recent_error_words_stream=recent_error_words_stream,
            due_progress_map=due_progress_map,
        )


recommendation_scoring_service = RecommendationScoringService()
