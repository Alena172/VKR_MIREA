from __future__ import annotations

from app.modules.learning.review.contracts import (
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


def to_word_progress_tracking_dto(*, word: str, tracked: bool) -> WordProgressTrackingDTO:
    return WordProgressTrackingDTO(
        word=word,
        tracked=tracked,
    )


def to_learning_progress_update_result_dto(
    *,
    updated_words: list[str],
) -> LearningProgressUpdateResultDTO:
    return LearningProgressUpdateResultDTO(updated_words=list(updated_words))


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


def to_review_queue_item_dto(
    *,
    word: str,
    russian_translation: str | None,
    next_review_at,
    error_count: int,
    correct_streak: int,
    status,
) -> ReviewQueueItemDTO:
    return ReviewQueueItemDTO(
        word=word,
        russian_translation=russian_translation,
        next_review_at=next_review_at,
        error_count=error_count,
        correct_streak=correct_streak,
        status=status,
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
    status,
) -> WordProgressDTO:
    return WordProgressDTO(
        user_id=user_id,
        word=word,
        russian_translation=russian_translation,
        error_count=error_count,
        correct_streak=correct_streak,
        next_review_at=next_review_at,
        status=status,
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
    status,
) -> ReviewSessionItemDTO:
    return ReviewSessionItemDTO(
        word=word,
        russian_translation=russian_translation,
        context_definition=context_definition,
        next_review_at=next_review_at,
        error_count=error_count,
        correct_streak=correct_streak,
        status=status,
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
) -> WordProgressDeleteDTO:
    return WordProgressDeleteDTO(
        user_id=user_id,
        word=word,
        progress_deleted=progress_deleted,
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
