from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.learning_graph.application_service import learning_graph_application_service
from app.modules.learning_graph.contracts import (
    LearningGraphObservabilityDTO,
    LearningGraphOverviewDTO,
    RecommendationsResultDTO,
    SemanticUpsertResultDTO,
    SenseAnchorsDTO,
    UserInterestsDTO,
)
from app.modules.learning_graph.schemas import (
    InterestUpsertRequest,
    InterestItem,
    LearningGraphObservabilityResponse,
    LearningGraphOverviewResponse,
    RecommendationsResponse,
    SemanticUpsertRequest,
    SemanticUpsertResponse,
    SenseAnchorsResponse,
    StrategyDistributionMetric,
    StrategyLatencyMetric,
    TopicClusterRead,
    UserInterestsResponse,
    WordSenseRead,
)

router = APIRouter(prefix="/learning-graph", tags=["learning_graph"])


def _to_user_interests_response(result: UserInterestsDTO) -> UserInterestsResponse:
    return UserInterestsResponse(
        user_id=result.user_id,
        interests=[
            InterestItem(interest=item.interest, weight=item.weight)
            for item in result.interests
        ],
    )


def _to_overview_response(result: LearningGraphOverviewDTO) -> LearningGraphOverviewResponse:
    return LearningGraphOverviewResponse(
        user_id=result.user_id,
        interests_count=result.interests_count,
        topic_clusters_count=result.topic_clusters_count,
        word_senses_count=result.word_senses_count,
        mistake_events_count=result.mistake_events_count,
        graph_edges_count=result.graph_edges_count,
        top_interests=result.top_interests,
        top_clusters=result.top_clusters,
        top_mistake_tags=result.top_mistake_tags,
    )


def _to_semantic_upsert_response(result: SemanticUpsertResultDTO) -> SemanticUpsertResponse:
    cluster = None
    if result.cluster is not None:
        cluster = TopicClusterRead(
            id=result.cluster.id,
            key=result.cluster.key,
            name=result.cluster.name,
            description=result.cluster.description,
        )
    return SemanticUpsertResponse(
        user_id=result.user_id,
        created_new_sense=result.created_new_sense,
        semantic_duplicate_of_id=result.semantic_duplicate_of_id,
        sense=WordSenseRead(
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


def _to_recommendations_response(result: RecommendationsResultDTO) -> RecommendationsResponse:
    return RecommendationsResponse(
        user_id=result.user_id,
        mode=result.mode,
        items=[
            {
                "english_lemma": item.english_lemma,
                "russian_translation": item.russian_translation,
                "topic_cluster": item.topic_cluster,
                "score": item.score,
                "reasons": item.reasons,
                "strategy_sources": item.strategy_sources,
                "primary_strategy": item.primary_strategy,
                "mistake_count": item.mistake_count,
            }
            for item in result.items
        ],
    )


def _to_observability_response(result: LearningGraphObservabilityDTO) -> LearningGraphObservabilityResponse:
    return LearningGraphObservabilityResponse(
        user_id=result.user_id,
        generated_at=result.generated_at,
        last_updated=result.last_updated,
        total_requests=result.total_requests,
        empty_recommendations_share=result.empty_recommendations_share,
        weak_recommendations_share=result.weak_recommendations_share,
        avg_items_per_response=result.avg_items_per_response,
        avg_top_score=result.avg_top_score,
        avg_mean_score=result.avg_mean_score,
        weak_score_threshold=result.weak_score_threshold,
        strategy_latency=[
            StrategyLatencyMetric(
                strategy=item.strategy,
                calls=item.calls,
                avg_ms=item.avg_ms,
                p95_ms=item.p95_ms,
                max_ms=item.max_ms,
                last_ms=item.last_ms,
            )
            for item in result.strategy_latency
        ],
        primary_strategy_distribution=[
            StrategyDistributionMetric(
                strategy=item.strategy,
                count=item.count,
                share=item.share,
            )
            for item in result.primary_strategy_distribution
        ],
    )


def _to_sense_anchors_response(result: SenseAnchorsDTO) -> SenseAnchorsResponse:
    return SenseAnchorsResponse(
        user_id=result.user_id,
        english_lemma=result.english_lemma,
        anchors=[
            {
                "word_sense_id": item.word_sense_id,
                "english_lemma": item.english_lemma,
                "russian_translation": item.russian_translation,
                "semantic_key": item.semantic_key,
                "relation_type": item.relation_type,
                "score": item.score,
                "topic_cluster": item.topic_cluster,
            }
            for item in result.anchors
        ],
    )


@router.get("/me/overview", response_model=LearningGraphOverviewResponse)
def get_learning_graph_overview_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LearningGraphOverviewResponse:
    return _to_overview_response(learning_graph_application_service.get_overview(
        db=db,
        current_user_id=current_user_id,
    ))


@router.get("/me/interests", response_model=UserInterestsResponse)
def list_interests_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserInterestsResponse:
    return _to_user_interests_response(learning_graph_application_service.list_interests(
        db=db,
        current_user_id=current_user_id,
    ))


@router.put("/me/interests", response_model=UserInterestsResponse)
def upsert_interests_me(
    payload: InterestUpsertRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserInterestsResponse:
    return _to_user_interests_response(learning_graph_application_service.upsert_interests(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    ))


@router.post("/me/semantic-upsert", response_model=SemanticUpsertResponse)
def semantic_upsert_me(
    payload: SemanticUpsertRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SemanticUpsertResponse:
    return _to_semantic_upsert_response(learning_graph_application_service.semantic_upsert(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    ))


@router.get("/me/recommendations", response_model=RecommendationsResponse)
def get_recommendations_me(
    mode: Literal["interest", "weakness", "mixed"] = Query(default="mixed"),
    limit: int = Query(default=10, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RecommendationsResponse:
    return _to_recommendations_response(learning_graph_application_service.get_recommendations(
        db=db,
        mode=mode,
        limit=limit,
        current_user_id=current_user_id,
    ))


@router.get("/me/observability", response_model=LearningGraphObservabilityResponse)
def get_observability_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LearningGraphObservabilityResponse:
    return _to_observability_response(learning_graph_application_service.get_observability(
        db=db,
        current_user_id=current_user_id,
    ))


@router.get("/me/anchors", response_model=SenseAnchorsResponse)
def get_anchors_me(
    english_lemma: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SenseAnchorsResponse:
    return _to_sense_anchors_response(learning_graph_application_service.get_anchors(
        db=db,
        english_lemma=english_lemma,
        limit=limit,
        current_user_id=current_user_id,
    ))
