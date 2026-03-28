from __future__ import annotations

from app.modules.context_memory.contracts import (
    ContextGarbageCleanupDTO,
    ContextRecommendationsDTO,
    EffectiveCefrDTO,
    LearningProgressUpdateResultDTO,
    MasteredLemmaDTO,
    ProgressSnapshotDTO,
    ReviewPlanDTO,
    ReviewQueueBulkSubmitDTO,
    ReviewQueueItemDTO,
    ReviewQueueResponseDTO,
    ReviewSessionItemDTO,
    ReviewSessionStartDTO,
    ReviewSummaryDTO,
    WordProgressDTO,
    WordProgressDeleteDTO,
    WordProgressListDTO,
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


def to_context_recommendations_dto(
    *,
    user_id: int,
    words: list[str],
    recent_error_words: list[str],
    difficult_words: list[str],
    scores: dict[str, float],
    next_review_at: dict[str, object],
) -> ContextRecommendationsDTO:
    return ContextRecommendationsDTO(
        user_id=user_id,
        words=list(words),
        recent_error_words=list(recent_error_words),
        difficult_words=list(difficult_words),
        scores=dict(scores),
        next_review_at=dict(next_review_at),
    )


def to_review_queue_item_dto(
    *,
    word: str,
    russian_translation: str | None,
    next_review_at,
    error_count: int,
    correct_streak: int,
) -> ReviewQueueItemDTO:
    return ReviewQueueItemDTO(
        word=word,
        russian_translation=russian_translation,
        next_review_at=next_review_at,
        error_count=error_count,
        correct_streak=correct_streak,
    )


def to_review_queue_response_dto(
    *,
    user_id: int,
    total_due: int,
    items: list[ReviewQueueItemDTO],
) -> ReviewQueueResponseDTO:
    return ReviewQueueResponseDTO(
        user_id=user_id,
        total_due=total_due,
        items=list(items),
    )


def to_word_progress_dto(
    *,
    user_id: int,
    word: str,
    russian_translation: str | None,
    error_count: int,
    correct_streak: int,
    next_review_at,
) -> WordProgressDTO:
    return WordProgressDTO(
        user_id=user_id,
        word=word,
        russian_translation=russian_translation,
        error_count=error_count,
        correct_streak=correct_streak,
        next_review_at=next_review_at,
    )


def to_word_progress_list_dto(
    *,
    user_id: int,
    total: int,
    limit: int,
    offset: int,
    items: list[WordProgressDTO],
) -> WordProgressListDTO:
    return WordProgressListDTO(
        user_id=user_id,
        total=total,
        limit=limit,
        offset=offset,
        items=list(items),
    )


def to_review_queue_bulk_submit_dto(
    *,
    user_id: int,
    updated: list[WordProgressDTO],
) -> ReviewQueueBulkSubmitDTO:
    return ReviewQueueBulkSubmitDTO(
        user_id=user_id,
        updated=list(updated),
    )


def to_review_session_item_dto(
    *,
    word: str,
    russian_translation: str | None,
    context_definition: str | None,
    next_review_at,
    error_count: int,
    correct_streak: int,
) -> ReviewSessionItemDTO:
    return ReviewSessionItemDTO(
        word=word,
        russian_translation=russian_translation,
        context_definition=context_definition,
        next_review_at=next_review_at,
        error_count=error_count,
        correct_streak=correct_streak,
    )


def to_review_session_start_dto(
    *,
    user_id: int,
    mode: str,
    total_items: int,
    items: list[ReviewSessionItemDTO],
) -> ReviewSessionStartDTO:
    return ReviewSessionStartDTO(
        user_id=user_id,
        mode=mode,
        total_items=total_items,
        items=list(items),
    )


def to_word_progress_delete_dto(
    *,
    user_id: int,
    word: str,
    progress_deleted: bool,
    removed_from_difficult_words: bool,
) -> WordProgressDeleteDTO:
    return WordProgressDeleteDTO(
        user_id=user_id,
        word=word,
        progress_deleted=progress_deleted,
        removed_from_difficult_words=removed_from_difficult_words,
    )


def to_review_plan_dto(
    *,
    user_id: int,
    due_count: int,
    upcoming_count: int,
    due_now: list[ReviewQueueItemDTO],
    upcoming: list[ReviewQueueItemDTO],
    recommended_words: list[str],
) -> ReviewPlanDTO:
    return ReviewPlanDTO(
        user_id=user_id,
        due_count=due_count,
        upcoming_count=upcoming_count,
        due_now=list(due_now),
        upcoming=list(upcoming),
        recommended_words=list(recommended_words),
    )


def to_context_garbage_cleanup_dto(
    *,
    user_id: int,
    removed_word_progress: int,
    removed_difficult_words: int,
) -> ContextGarbageCleanupDTO:
    return ContextGarbageCleanupDTO(
        user_id=user_id,
        removed_word_progress=removed_word_progress,
        removed_difficult_words=removed_difficult_words,
    )
