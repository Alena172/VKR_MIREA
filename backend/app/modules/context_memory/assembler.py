from __future__ import annotations

from app.modules.context_memory.contracts import (
    EffectiveCefrDTO,
    LearningProgressUpdateResultDTO,
    MasteredLemmaDTO,
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
