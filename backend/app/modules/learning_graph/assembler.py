from __future__ import annotations

from app.modules.learning_graph.contracts import (
    RecommendationItemDTO,
    RegisteredVocabularySenseDTO,
    WordAnchorDTO,
)
from app.modules.learning_graph.repository import SemanticUpsertResult
from app.modules.learning_graph.schemas import RecommendationItem, SenseAnchorItem


def to_recommendation_item_dto(item: RecommendationItem) -> RecommendationItemDTO:
    return RecommendationItemDTO(
        english_lemma=item.english_lemma,
        russian_translation=item.russian_translation,
        topic_cluster=item.topic_cluster,
        score=item.score,
        reasons=list(item.reasons),
        strategy_sources=list(item.strategy_sources),
        primary_strategy=item.primary_strategy,
        mistake_count=item.mistake_count,
    )


def to_word_anchor_dto(item: SenseAnchorItem) -> WordAnchorDTO:
    return WordAnchorDTO(
        word_sense_id=item.word_sense_id,
        english_lemma=item.english_lemma,
        russian_translation=item.russian_translation,
        semantic_key=item.semantic_key,
        relation_type=item.relation_type,
        score=item.score,
        topic_cluster=item.topic_cluster,
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
