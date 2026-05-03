from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.identity.auth.dependencies import get_current_user_id
from app.modules.learning_graph.application_service import learning_graph_application_service
from app.modules.learning_graph.contracts import (
    InterestWordsDTO,
    SemanticUpsertResultDTO,
    SenseAnchorsDTO,
    UserInterestsDTO,
)
from app.modules.learning_graph.schemas import (
    InterestItem,
    InterestWordsResponse,
    SemanticUpsertRequest,
    SemanticUpsertResponse,
    SenseAnchorsResponse,
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


def _to_semantic_upsert_response(result: SemanticUpsertResultDTO) -> SemanticUpsertResponse:
    return SemanticUpsertResponse(
        user_id=result.user_id,
        created_new_sense=result.created_new_sense,
        sense=WordSenseRead(
            id=result.sense.id,
            english_lemma=result.sense.english_lemma,
            semantic_key=result.sense.semantic_key,
            russian_translation=result.sense.russian_translation,
        ),
    )


def _to_interest_words_response(result: InterestWordsDTO) -> InterestWordsResponse:
    return InterestWordsResponse(
        user_id=result.user_id,
        items=[
            {
                "english_lemma": item.english_lemma,
                "russian_translation": item.russian_translation,
                "score": item.score,
                "reasons": item.reasons,
                "profile_signals": item.profile_signals,
                "primary_signal": item.primary_signal,
            }
            for item in result.items
        ],
    )


def _to_sense_anchors_response(result: SenseAnchorsDTO) -> SenseAnchorsResponse:
    return SenseAnchorsResponse(
        user_id=result.user_id,
        english_lemma=result.english_lemma,
        anchors=[
            {
                "english_lemma": item.english_lemma,
                "russian_translation": item.russian_translation,
                "relation_type": item.relation_type,
                "score": item.score,
            }
            for item in result.anchors
        ],
    )


@router.get("/me/interests", response_model=UserInterestsResponse)
def list_interests_me(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserInterestsResponse:
    return _to_user_interests_response(learning_graph_application_service.list_interests(
        db=db,
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


@router.get("/me/interest-words", response_model=InterestWordsResponse)
def get_interest_words_me(
    limit: int = Query(default=10, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> InterestWordsResponse:
    return _to_interest_words_response(learning_graph_application_service.get_interest_words(
        db=db,
        limit=limit,
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
