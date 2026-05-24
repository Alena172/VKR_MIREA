"""Эндпоинты графа интересов и тематических подсказок пользователя."""

from fastapi import APIRouter, Depends, Query

from app.modules.graph.schemas import (
    InterestUpsertRequest,
    InterestWordsResponse,
    UserInterestsResponse,
)
from app.modules.graph.service.graph import GraphService
from app.modules.identity.deps import get_current_user_id
from app.modules.vocabulary.service.items import VocabularyService

router = APIRouter(prefix="/learning-graph", tags=["graph"])


@router.get("/me/interests", response_model=UserInterestsResponse)
def list_interests_me(
    current_user_id: int = Depends(get_current_user_id),
    service: GraphService = Depends(),
) -> UserInterestsResponse:
    """Возвращает текущие интересы пользователя в графе тем."""
    return service.list_interests(current_user_id=current_user_id)


@router.put("/me/interests", response_model=UserInterestsResponse)
def upsert_interests_me(
    payload: InterestUpsertRequest,
    current_user_id: int = Depends(get_current_user_id),
    service: GraphService = Depends(),
) -> UserInterestsResponse:
    """Создаёт или обновляет список пользовательских интересов."""
    return service.upsert_interests(payload=payload, current_user_id=current_user_id)


@router.get("/me/interest-words", response_model=InterestWordsResponse)
def get_interest_words_me(
    limit: int = Query(default=10, ge=1),
    current_user_id: int = Depends(get_current_user_id),
    graph_service: GraphService = Depends(),
    vocab_service: VocabularyService = Depends(),
) -> InterestWordsResponse:
    """Подбирает слова по интересам, которых ещё нет в личном словаре."""
    saved_lemmas = {
        item.english_lemma.strip().lower()
        for item in vocab_service.list_user_items(user_id=current_user_id)
        if item.english_lemma
    }
    return graph_service.get_interest_words(
        limit=limit,
        current_user_id=current_user_id,
        saved_lemmas=saved_lemmas,
    )
