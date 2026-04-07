from __future__ import annotations

from app.modules.learning_graph.contracts import (
    InterestItemDTO,
    RecommendationItemDTO,
    RecommendationsResultDTO,
    RegisteredVocabularySenseDTO,
    SemanticUpsertResultDTO,
    SenseAnchorsDTO,
    UserInterestsDTO,
    WordSenseDTO,
    WordAnchorDTO,
)
from app.modules.learning_graph.repository import SemanticUpsertResult
from app.modules.learning_graph.schemas import (
    InterestItem,
    RecommendationItem,
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


def to_recommendation_item_dto(item: RecommendationItem) -> RecommendationItemDTO:
    return RecommendationItemDTO(
        english_lemma=item.english_lemma,
        russian_translation=item.russian_translation,
        score=item.score,
        reasons=list(item.reasons),
        strategy_sources=list(item.strategy_sources),
        primary_strategy=item.primary_strategy,
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


def to_recommendations_result_dto(
    *,
    user_id: int,
    mode: str,
    items: list[RecommendationItem],
) -> RecommendationsResultDTO:
    return RecommendationsResultDTO(
        user_id=user_id,
        mode=mode,
        items=[to_recommendation_item_dto(item) for item in items],
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
