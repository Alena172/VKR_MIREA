from app.modules.learning.contracts import (
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
)
from app.modules.learning.schemas.review_schemas import (
    ProgressSnapshot,
    ReviewPlanResponse,
    ReviewQueueBulkSubmitResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
    ReviewSessionItem,
    ReviewSessionStartResponse,
    ReviewSummary,
    WordProgressDeleteResponse,
    WordProgressListResponse,
    WordProgressRead,
)


def to_review_queue_item_response(item: ReviewQueueItemDTO) -> ReviewQueueItem:
    return ReviewQueueItem(
        word=item.word,
        russian_translation=item.russian_translation,
        next_review_at=item.next_review_at,
        error_count=item.error_count,
        correct_streak=item.correct_streak,
        status=item.status,
    )


def to_word_progress_response(item: WordProgressDTO) -> WordProgressRead:
    return WordProgressRead(
        user_id=item.user_id,
        word=item.word,
        russian_translation=item.russian_translation,
        error_count=item.error_count,
        correct_streak=item.correct_streak,
        next_review_at=item.next_review_at,
        status=item.status,
    )


def to_review_queue_response(result: ReviewQueueResponseDTO) -> ReviewQueueResponse:
    return ReviewQueueResponse(
        user_id=result.user_id,
        total_due=result.total_due,
        items=[to_review_queue_item_response(item) for item in result.items],
    )


def to_review_queue_bulk_submit_response(result: ReviewQueueBulkSubmitDTO) -> ReviewQueueBulkSubmitResponse:
    return ReviewQueueBulkSubmitResponse(
        user_id=result.user_id,
        updated=[to_word_progress_response(item) for item in result.updated],
    )


def to_review_session_item_response(item: ReviewSessionItemDTO) -> ReviewSessionItem:
    return ReviewSessionItem(
        word=item.word,
        russian_translation=item.russian_translation,
        context_definition=item.context_definition,
        next_review_at=item.next_review_at,
        error_count=item.error_count,
        correct_streak=item.correct_streak,
        status=item.status,
    )


def to_review_session_start_response(result: ReviewSessionStartDTO) -> ReviewSessionStartResponse:
    return ReviewSessionStartResponse(
        user_id=result.user_id,
        mode=result.mode,
        total_items=result.total_items,
        items=[to_review_session_item_response(item) for item in result.items],
    )


def to_word_progress_list_response(result: WordProgressListDTO) -> WordProgressListResponse:
    return WordProgressListResponse(
        user_id=result.user_id,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        items=[to_word_progress_response(item) for item in result.items],
    )


def to_word_progress_delete_response(result: WordProgressDeleteDTO) -> WordProgressDeleteResponse:
    return WordProgressDeleteResponse(
        user_id=result.user_id,
        word=result.word,
        progress_deleted=result.progress_deleted,
    )


def to_review_plan_response(result: ReviewPlanDTO) -> ReviewPlanResponse:
    return ReviewPlanResponse(
        user_id=result.user_id,
        due_count=result.due_count,
        upcoming_count=result.upcoming_count,
        due_now=[to_review_queue_item_response(item) for item in result.due_now],
        upcoming=[to_review_queue_item_response(item) for item in result.upcoming],
        recommended_words=result.recommended_words,
    )


def to_progress_snapshot_response(result) -> ProgressSnapshot:
    return ProgressSnapshot(
        user_id=result.user_id,
        total_sessions=result.total_sessions,
        avg_accuracy=result.avg_accuracy,
    )


def to_review_summary_response(result: ReviewSummaryDTO) -> ReviewSummary:
    return ReviewSummary(
        user_id=result.user_id,
        total_tracked=result.total_tracked,
        due_now=result.due_now,
        mastered=result.mastered,
        troubled=result.troubled,
    )
