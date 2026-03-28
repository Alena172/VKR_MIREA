from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InterestItemDTO:
    interest: str
    weight: float


@dataclass(frozen=True)
class TopicClusterDTO:
    id: int
    key: str
    name: str
    description: str | None


@dataclass(frozen=True)
class RecommendationItemDTO:
    english_lemma: str
    russian_translation: str
    topic_cluster: str | None
    score: float
    reasons: list[str]
    strategy_sources: list[str]
    primary_strategy: str | None
    mistake_count: int


@dataclass(frozen=True)
class WordAnchorDTO:
    word_sense_id: int
    english_lemma: str
    russian_translation: str
    semantic_key: str
    relation_type: str
    score: float
    topic_cluster: str | None


@dataclass(frozen=True)
class RegisteredVocabularySenseDTO:
    sense_id: int
    english_lemma: str
    semantic_key: str
    cluster_id: int | None
    created_new_sense: bool
    semantic_duplicate_of_id: int | None


@dataclass(frozen=True)
class UserInterestsDTO:
    user_id: int
    interests: list[InterestItemDTO]


@dataclass(frozen=True)
class WordSenseDTO:
    id: int
    english_lemma: str
    semantic_key: str
    russian_translation: str
    context_definition_ru: str | None
    source_sentence: str | None
    source_url: str | None
    topic_cluster_id: int | None
    created_at: datetime


@dataclass(frozen=True)
class SemanticUpsertResultDTO:
    user_id: int
    created_new_sense: bool
    semantic_duplicate_of_id: int | None
    sense: WordSenseDTO
    cluster: TopicClusterDTO | None


@dataclass(frozen=True)
class LearningGraphOverviewDTO:
    user_id: int
    interests_count: int
    topic_clusters_count: int
    word_senses_count: int
    mistake_events_count: int
    graph_edges_count: int
    top_interests: list[str]
    top_clusters: list[str]
    top_mistake_tags: list[str]


@dataclass(frozen=True)
class RecommendationsResultDTO:
    user_id: int
    mode: str
    items: list[RecommendationItemDTO]


@dataclass(frozen=True)
class StrategyLatencyMetricDTO:
    strategy: str
    calls: int
    avg_ms: float
    p95_ms: float
    max_ms: float
    last_ms: float


@dataclass(frozen=True)
class StrategyDistributionMetricDTO:
    strategy: str
    count: int
    share: float


@dataclass(frozen=True)
class LearningGraphObservabilityDTO:
    user_id: int
    generated_at: datetime
    last_updated: datetime
    total_requests: int
    empty_recommendations_share: float
    weak_recommendations_share: float
    avg_items_per_response: float
    avg_top_score: float
    avg_mean_score: float
    weak_score_threshold: float
    strategy_latency: list[StrategyLatencyMetricDTO]
    primary_strategy_distribution: list[StrategyDistributionMetricDTO]


@dataclass(frozen=True)
class SenseAnchorsDTO:
    user_id: int
    english_lemma: str
    anchors: list[WordAnchorDTO]
