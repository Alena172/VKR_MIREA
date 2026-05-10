from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.graph.schemas import (
    InterestUpsertRequest,
    InterestWordsResponse,
    SemanticUpsertRequest,
    SemanticUpsertResponse,
    SenseAnchorsResponse,
    UserInterestsResponse,
)
from app.modules.graph.service.graph import graph_service
from app.modules.identity.deps import get_current_user_id
from app.modules.review.service.srs import srs_service

router = APIRouter(prefix="/learning-graph", tags=["graph"])


@router.get("/me/interests", response_model=UserInterestsResponse)
def list_interests_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserInterestsResponse:
    return graph_service.list_interests(db=db, current_user_id=current_user_id)


@router.put("/me/interests", response_model=UserInterestsResponse)
def upsert_interests_me(
    payload: InterestUpsertRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserInterestsResponse:
    return graph_service.upsert_interests(db=db, payload=payload, current_user_id=current_user_id)


@router.post("/me/semantic-upsert", response_model=SemanticUpsertResponse)
def semantic_upsert_me(
    payload: SemanticUpsertRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SemanticUpsertResponse:
    return graph_service.semantic_upsert(db=db, payload=payload, current_user_id=current_user_id)


@router.get("/me/interest-words", response_model=InterestWordsResponse)
def get_interest_words_me(
    limit: int = Query(default=10, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> InterestWordsResponse:
    known_lemmas = srs_service.list_mastered_lemmas(db=db, user_id=current_user_id)
    return graph_service.get_interest_words(
        db=db,
        limit=limit,
        current_user_id=current_user_id,
        known_lemmas=known_lemmas,
    )


@router.get("/me/anchors", response_model=SenseAnchorsResponse)
def get_anchors_me(
    english_lemma: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=50),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SenseAnchorsResponse:
    return graph_service.get_anchors(
        db=db,
        english_lemma=english_lemma,
        limit=limit,
        current_user_id=current_user_id,
    )
