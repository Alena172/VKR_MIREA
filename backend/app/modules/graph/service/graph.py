from __future__ import annotations

from fastapi import Depends

from app.core.db import transaction
from app.modules.graph.repository import GraphRepository
from app.modules.identity.service import IdentityService
from app.modules.graph.schemas import (
    InterestItem,
    InterestUpsertRequest,
    InterestWordItem,
    InterestWordsResponse,
    UserInterestsResponse,
)


class GraphService:
    """Сервис уровня application для профиля интересов пользователя."""

    def __init__(
        self,
        repo: GraphRepository = Depends(),
        identity_service: IdentityService = Depends(),
    ) -> None:
        self._repo = repo
        self._identity_service = identity_service

    def _get_user_or_404(self, user_id: int):
        return self._identity_service.get_user_or_404(user_id=user_id)

    def list_interests(self, *, current_user_id: int) -> UserInterestsResponse:
        self._get_user_or_404(current_user_id)
        interests = self._repo.list_interests(current_user_id)
        return UserInterestsResponse(
            user_id=current_user_id,
            interests=[InterestItem(interest=i.interest, weight=i.weight) for i in interests],
        )

    def upsert_interests(
        self,
        *,
        payload: InterestUpsertRequest,
        current_user_id: int,
    ) -> UserInterestsResponse:
        self._get_user_or_404(current_user_id)
        with transaction(self._repo._db):
            updated = self._repo.upsert_interests(current_user_id, payload.interests)
        return UserInterestsResponse(
            user_id=current_user_id,
            interests=[InterestItem(interest=i.interest, weight=i.weight) for i in updated],
        )

    def get_interest_words(
        self,
        *,
        limit: int,
        current_user_id: int,
        saved_lemmas: set[str],
    ) -> InterestWordsResponse:
        self._get_user_or_404(current_user_id)
        items = self._repo.list_interest_words(
            user_id=current_user_id,
            limit=limit,
            saved_lemmas=saved_lemmas,
        )
        return InterestWordsResponse(
            user_id=current_user_id,
            items=[
                InterestWordItem(
                    english_lemma=item.english_lemma,
                    russian_translation=item.russian_translation,
                    score=item.score,
                    reasons=item.reasons,
                    profile_signals=item.profile_signals,
                    primary_signal=item.primary_signal,
                )
                for item in items
            ],
        )

    def register_word_topic(
        self,
        *,
        user_id: int,
        english_lemma: str,
        russian_translation: str,
        context_definition_ru: str | None,
        source_sentence: str | None,
    ) -> int | None:
        """Инферирует тему слова, создаёт кластер если нужно, обновляет интересы.

        Возвращает topic_cluster_id для записи в dictionary_entries.
        """
        cluster_key, display_name = self._repo.infer_topic(
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            context_definition_ru=context_definition_ru,
            source_sentence=source_sentence,
        )
        cluster = self._repo.ensure_cluster(cluster_key=cluster_key, display_name=display_name)
        self._repo.increase_interest(
            user_id=user_id,
            cluster_key=cluster_key,
            display_name=display_name,
            confidence=0.55,
        )
        return cluster.id
