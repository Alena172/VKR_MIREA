from __future__ import annotations

from app.modules.learning_graph.contracts import (
    InterestItemDTO,
    InterestWordItemDTO,
    InterestWordsDTO,
    RegisteredVocabularySenseDTO,
    SemanticUpsertResultDTO,
    SenseAnchorsDTO,
    UserInterestsDTO,
    WordSenseDTO,
    WordAnchorDTO,
)
from app.modules.learning_graph.repositories.repository import SemanticUpsertResult
from app.modules.learning_graph.schemas.schemas import (
    InterestItem,
    InterestWordItem,
    SenseAnchorItem,
)


def to_interest_item_dto(item: InterestItem) -> InterestItemDTO:
    return InterestItemDTO(
        interest=item.interest,
        weight=item.weight,
    )


def to_word_sense_dto(
    *,
    id: int,
    english_lemma: str,
    semantic_key: str,
    russian_translation: str,
) -> WordSenseDTO:
    return WordSenseDTO(
        id=id,
        english_lemma=english_lemma,
        semantic_key=semantic_key,
        russian_translation=russian_translation,
    )


def to_interest_word_item_dto(item: InterestWordItem) -> InterestWordItemDTO:
    return InterestWordItemDTO(
        english_lemma=item.english_lemma,
        russian_translation=item.russian_translation,
        score=item.score,
        reasons=list(item.reasons),
        profile_signals=list(item.profile_signals),
        primary_signal=item.primary_signal,
    )


def to_word_anchor_dto(item: SenseAnchorItem) -> WordAnchorDTO:
    return WordAnchorDTO(
        english_lemma=item.english_lemma,
        russian_translation=item.russian_translation,
        relation_type=item.relation_type,
        score=item.score,
    )


def to_registered_vocabulary_sense_dto(result: SemanticUpsertResult) -> RegisteredVocabularySenseDTO:
    return RegisteredVocabularySenseDTO(
        sense_id=result.sense.id,
        english_lemma=result.sense.english_lemma,
        semantic_key=result.sense.semantic_key,
        cluster_id=result.sense.topic_cluster_id,
        created_new_sense=result.created_new,
        semantic_duplicate_of_id=result.duplicate_of_id,
    )


def to_user_interests_dto(*, user_id: int, interests: list[InterestItem]) -> UserInterestsDTO:
    return UserInterestsDTO(
        user_id=user_id,
        interests=[to_interest_item_dto(item) for item in interests],
    )


def to_semantic_upsert_result_dto(
    *,
    user_id: int,
    result: SemanticUpsertResult,
) -> SemanticUpsertResultDTO:
    return SemanticUpsertResultDTO(
        user_id=user_id,
        created_new_sense=result.created_new,
        sense=to_word_sense_dto(
            id=result.sense.id,
            english_lemma=result.sense.english_lemma,
            semantic_key=result.sense.semantic_key,
            russian_translation=result.sense.russian_translation,
        ),
    )


def to_interest_words_dto(
    *,
    user_id: int,
    mode: str,
    items: list[InterestWordItem],
) -> InterestWordsDTO:
    return InterestWordsDTO(
        user_id=user_id,
        mode=mode,
        items=[to_interest_word_item_dto(item) for item in items],
    )


def to_sense_anchors_dto(
    *,
    user_id: int,
    english_lemma: str,
    anchors: list[SenseAnchorItem],
) -> SenseAnchorsDTO:
    return SenseAnchorsDTO(
        user_id=user_id,
        english_lemma=english_lemma.strip().lower(),
        anchors=[to_word_anchor_dto(item) for item in anchors],
    )
