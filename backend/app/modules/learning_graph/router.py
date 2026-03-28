from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.learning_graph.application_service import learning_graph_application_service
from app.modules.learning_graph.schemas import (
    InterestUpsertRequest,
    LearningGraphObservabilityResponse,
    LearningGraphOverviewResponse,
    RecommendationsResponse,
    SemanticUpsertRequest,
    SemanticUpsertResponse,
    SenseAnchorsResponse,
    UserInterestsResponse,
)

router = APIRouter(prefix="/learning-graph", tags=["learning_graph"])


@router.get("/me/overview", response_model=LearningGraphOverviewResponse)
def get_learning_graph_overview_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LearningGraphOverviewResponse:
    return learning_graph_application_service.get_overview(
        db=db,
        current_user_id=current_user_id,
    )


@router.get("/me/interests", response_model=UserInterestsResponse)
def list_interests_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserInterestsResponse:
    return learning_graph_application_service.list_interests(
        db=db,
        current_user_id=current_user_id,
    )


@router.put("/me/interests", response_model=UserInterestsResponse)
def upsert_interests_me(
    payload: InterestUpsertRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserInterestsResponse:
    return learning_graph_application_service.upsert_interests(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )


@router.post("/me/semantic-upsert", response_model=SemanticUpsertResponse)
def semantic_upsert_me(
    payload: SemanticUpsertRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SemanticUpsertResponse:
    return learning_graph_application_service.semantic_upsert(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )


@router.get("/me/recommendations", response_model=RecommendationsResponse)
def get_recommendations_me(
    mode: Literal["interest", "weakness", "mixed"] = Query(default="mixed"),
    limit: int = Query(default=10, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RecommendationsResponse:
    return learning_graph_application_service.get_recommendations(
        db=db,
        mode=mode,
        limit=limit,
        current_user_id=current_user_id,
    )


@router.get("/me/observability", response_model=LearningGraphObservabilityResponse)
def get_observability_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LearningGraphObservabilityResponse:
    return learning_graph_application_service.get_observability(
        db=db,
        current_user_id=current_user_id,
    )


@router.get("/me/anchors", response_model=SenseAnchorsResponse)
def get_anchors_me(
    english_lemma: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SenseAnchorsResponse:
    return learning_graph_application_service.get_anchors(
        db=db,
        english_lemma=english_lemma,
        limit=limit,
        current_user_id=current_user_id,
    )
