from __future__ import annotations

from app.modules.context_memory.contracts import (
    EffectiveCefrDTO,
    LearningProgressUpdateResultDTO,
    MasteredLemmaDTO,
    ProgressSnapshotDTO,
    ReviewSummaryDTO,
    WordProgressTrackingDTO,
)


def to_effective_cefr_dto(cefr_level: str) -> EffectiveCefrDTO:
    return EffectiveCefrDTO(cefr_level=cefr_level)


def to_word_progress_tracking_dto(*, word: str, tracked: bool) -> WordProgressTrackingDTO:
    return WordProgressTrackingDTO(
        word=word,
        tracked=tracked,
    )


def to_learning_progress_update_result_dto(
    *,
    difficult_words_added: list[str],
) -> LearningProgressUpdateResultDTO:
    return LearningProgressUpdateResultDTO(difficult_words_added=list(difficult_words_added))


def to_mastered_lemma_dtos(words: set[str]) -> list[MasteredLemmaDTO]:
    return [MasteredLemmaDTO(word=word) for word in sorted(words)]


def to_progress_snapshot_dto(
    *,
    user_id: int,
    total_sessions: int,
    avg_accuracy: float,
) -> ProgressSnapshotDTO:
    return ProgressSnapshotDTO(
        user_id=user_id,
        total_sessions=total_sessions,
        avg_accuracy=avg_accuracy,
    )


def to_review_summary_dto(
    *,
    user_id: int,
    total_tracked: int,
    due_now: int,
    mastered: int,
    troubled: int,
) -> ReviewSummaryDTO:
    return ReviewSummaryDTO(
        user_id=user_id,
        total_tracked=total_tracked,
        due_now=due_now,
        mastered=mastered,
        troubled=troubled,
    )
