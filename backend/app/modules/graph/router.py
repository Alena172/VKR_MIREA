from fastapi import APIRouter, Depends, Query

from app.modules.graph.schemas import (
    InterestUpsertRequest,
    InterestWordsResponse,
    SemanticUpsertRequest,
    SemanticUpsertResponse,
    SenseAnchorsResponse,
    UserInterestsResponse,
)
from app.modules.graph.service.graph import GraphService
from app.modules.identity.deps import get_current_user_id
from app.modules.review.service.srs import SRSService

router = APIRouter(prefix="/learning-graph", tags=["graph"])


@router.get("/me/interests", response_model=UserInterestsResponse)
def list_interests_me(
    current_user_id: int = Depends(get_current_user_id),
    service: GraphService = Depends(),
) -> UserInterestsResponse:
    return service.list_interests(current_user_id=current_user_id)


@router.put("/me/interests", response_model=UserInterestsResponse)
def upsert_interests_me(
    payload: InterestUpsertRequest,
    current_user_id: int = Depends(get_current_user_id),
    service: GraphService = Depends(),
) -> UserInterestsResponse:
    return service.upsert_interests(payload=payload, current_user_id=current_user_id)


@router.post("/me/semantic-upsert", response_model=SemanticUpsertResponse)
def semantic_upsert_me(
    payload: SemanticUpsertRequest,
    current_user_id: int = Depends(get_current_user_id),
    service: GraphService = Depends(),
) -> SemanticUpsertResponse:
    return service.semantic_upsert(payload=payload, current_user_id=current_user_id)


@router.get("/me/interest-words", response_model=InterestWordsResponse)
def get_interest_words_me(
    limit: int = Query(default=10, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    graph_service: GraphService = Depends(),
    srs_service: SRSService = Depends(),
) -> InterestWordsResponse:
    known_lemmas = srs_service.list_mastered_lemmas(user_id=current_user_id)
    return graph_service.get_interest_words(
        limit=limit,
        current_user_id=current_user_id,
        known_lemmas=known_lemmas,
    )


@router.get("/me/anchors", response_model=SenseAnchorsResponse)
def get_anchors_me(
    english_lemma: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    service: GraphService = Depends(),
) -> SenseAnchorsResponse:
    return service.get_anchors(
        english_lemma=english_lemma,
        limit=limit,
        current_user_id=current_user_id,
    )
