from __future__ import annotations

from app.modules.learning_graph.contracts import (
    InterestItemDTO,
    LearningGraphObservabilityDTO,
    LearningGraphOverviewDTO,
    RecommendationItemDTO,
    RecommendationsResultDTO,
    RegisteredVocabularySenseDTO,
    SemanticUpsertResultDTO,
    SenseAnchorsDTO,
    StrategyDistributionMetricDTO,
    StrategyLatencyMetricDTO,
    TopicClusterDTO,
    UserInterestsDTO,
    WordSenseDTO,
    WordAnchorDTO,
)
from app.modules.learning_graph.repository import SemanticUpsertResult
from app.modules.learning_graph.schemas import (
    InterestItem,
    RecommendationItem,
    SenseAnchorItem,
    StrategyDistributionMetric,
    StrategyLatencyMetric,
)


def to_interest_item_dto(item: InterestItem) -> InterestItemDTO:
    return InterestItemDTO(
        interest=item.interest,
        weight=item.weight,
    )


def to_topic_cluster_dto(*, id: int, key: str, name: str, description: str | None) -> TopicClusterDTO:
    return TopicClusterDTO(
        id=id,
        key=key,
        name=name,
        description=description,
    )


def to_word_sense_dto(
    *,
    id: int,
    english_lemma: str,
    semantic_key: str,
    russian_translation: str,
    context_definition_ru: str | None,
    source_sentence: str | None,
    source_url: str | None,
    topic_cluster_id: int | None,
    created_at,
) -> WordSenseDTO:
    return WordSenseDTO(
        id=id,
        english_lemma=english_lemma,
        semantic_key=semantic_key,
        russian_translation=russian_translation,
        context_definition_ru=context_definition_ru,
        source_sentence=source_sentence,
        source_url=source_url,
        topic_cluster_id=topic_cluster_id,
        created_at=created_at,
    )


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
    cluster = None
    if result.cluster is not None:
        cluster = to_topic_cluster_dto(
            id=result.cluster.id,
            key=result.cluster.cluster_key,
            name=result.cluster.name,
            description=result.cluster.description,
        )
    return SemanticUpsertResultDTO(
        user_id=user_id,
        created_new_sense=result.created_new,
        semantic_duplicate_of_id=result.duplicate_of_id,
        sense=to_word_sense_dto(
            id=result.sense.id,
            english_lemma=result.sense.english_lemma,
            semantic_key=result.sense.semantic_key,
            russian_translation=result.sense.russian_translation,
            context_definition_ru=result.sense.context_definition_ru,
            source_sentence=result.sense.source_sentence,
            source_url=result.sense.source_url,
            topic_cluster_id=result.sense.topic_cluster_id,
            created_at=result.sense.created_at,
        ),
        cluster=cluster,
    )


def to_learning_graph_overview_dto(*, user_id: int, overview: dict) -> LearningGraphOverviewDTO:
    return LearningGraphOverviewDTO(
        user_id=user_id,
        interests_count=overview["interests_count"],
        topic_clusters_count=overview["topic_clusters_count"],
        word_senses_count=overview["word_senses_count"],
        mistake_events_count=overview["mistake_events_count"],
        graph_edges_count=overview["graph_edges_count"],
        top_interests=list(overview["top_interests"]),
        top_clusters=list(overview["top_clusters"]),
        top_mistake_tags=list(overview["top_mistake_tags"]),
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


def to_strategy_latency_metric_dto(item: StrategyLatencyMetric) -> StrategyLatencyMetricDTO:
    return StrategyLatencyMetricDTO(
        strategy=item.strategy,
        calls=item.calls,
        avg_ms=item.avg_ms,
        p95_ms=item.p95_ms,
        max_ms=item.max_ms,
        last_ms=item.last_ms,
    )


def to_strategy_distribution_metric_dto(
    item: StrategyDistributionMetric,
) -> StrategyDistributionMetricDTO:
    return StrategyDistributionMetricDTO(
        strategy=item.strategy,
        count=item.count,
        share=item.share,
    )


def to_learning_graph_observability_dto(*, user_id: int, snapshot: dict) -> LearningGraphObservabilityDTO:
    return LearningGraphObservabilityDTO(
        user_id=user_id,
        generated_at=snapshot["generated_at"],
        last_updated=snapshot["last_updated"],
        total_requests=snapshot["total_requests"],
        empty_recommendations_share=snapshot["empty_recommendations_share"],
        weak_recommendations_share=snapshot["weak_recommendations_share"],
        avg_items_per_response=snapshot["avg_items_per_response"],
        avg_top_score=snapshot["avg_top_score"],
        avg_mean_score=snapshot["avg_mean_score"],
        weak_score_threshold=snapshot["weak_score_threshold"],
        strategy_latency=[
            to_strategy_latency_metric_dto(item) for item in snapshot["strategy_latency"]
        ],
        primary_strategy_distribution=[
            to_strategy_distribution_metric_dto(item)
            for item in snapshot["primary_strategy_distribution"]
        ],
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
