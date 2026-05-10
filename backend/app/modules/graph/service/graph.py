from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.application import application_access, application_transaction
from app.modules.graph.repository import GraphRepository, graph_repository
from app.modules.graph.schemas import (
    InterestItem,
    InterestUpsertRequest,
    InterestWordItem,
    InterestWordsResponse,
    SemanticUpsertRequest,
    SemanticUpsertResponse,
    SenseAnchorItem,
    SenseAnchorsResponse,
    UserInterestsResponse,
    WordSenseRead,
)


class GraphService:
    """Application-сервис семантического профиля, интересов и смыслов слов."""

    def __init__(self, repo: GraphRepository) -> None:
        self._repo = repo

    def list_interests(
        self,
        *,
        db: Session,
        current_user_id: int,
    ) -> UserInterestsResponse:
        application_access.get_user_or_404(db=db, user_id=current_user_id)
        interests = self._repo.list_interests(db, current_user_id)
        return UserInterestsResponse(
            user_id=current_user_id,
            interests=[InterestItem(interest=i.display_name, weight=i.weight) for i in interests],
        )

    def upsert_interests(
        self,
        *,
        db: Session,
        payload: InterestUpsertRequest,
        current_user_id: int,
    ) -> UserInterestsResponse:
        application_access.get_user_or_404(db=db, user_id=current_user_id)
        updated = self._repo.upsert_interests(db, user_id=current_user_id, interests=payload.interests)
        return UserInterestsResponse(
            user_id=current_user_id,
            interests=[InterestItem(interest=i.display_name, weight=i.weight) for i in updated],
        )

    def semantic_upsert(
        self,
        *,
        db: Session,
        payload: SemanticUpsertRequest,
        current_user_id: int,
    ) -> SemanticUpsertResponse:
        application_access.get_user_or_404(db=db, user_id=current_user_id)
        try:
            with application_transaction.boundary(db=db):
                result = self._repo.semantic_upsert(
                    db,
                    user_id=current_user_id,
                    english_lemma=payload.english_lemma,
                    russian_translation=payload.russian_translation,
                    context_definition_ru=payload.context_definition_ru,
                    source_sentence=payload.source_sentence,
                    source_url=payload.source_url,
                    topic_hint=payload.topic_hint,
                    vocabulary_item_id=payload.vocabulary_item_id,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        db.refresh(result.sense)
        return SemanticUpsertResponse(
            user_id=current_user_id,
            created_new_sense=result.created_new,
            sense=WordSenseRead(
                id=result.sense.id,
                english_lemma=result.sense.english_lemma,
                semantic_key=result.sense.semantic_key,
                russian_translation=result.sense.russian_translation,
            ),
        )

    def get_interest_words(
        self,
        *,
        db: Session,
        limit: int,
        current_user_id: int,
        known_lemmas: set[str],
    ) -> InterestWordsResponse:
        application_access.get_user_or_404(db=db, user_id=current_user_id)
        items = self._repo.list_interest_words(
            db,
            user_id=current_user_id,
            limit=limit,
            known_lemmas=known_lemmas,
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

    def get_anchors(
        self,
        *,
        db: Session,
        english_lemma: str,
        limit: int,
        current_user_id: int,
    ) -> SenseAnchorsResponse:
        application_access.get_user_or_404(db=db, user_id=current_user_id)
        anchors = self._repo.list_anchors(
            db,
            user_id=current_user_id,
            english_lemma=english_lemma,
            limit=limit,
        )
        return SenseAnchorsResponse(
            user_id=current_user_id,
            english_lemma=english_lemma,
            anchors=[
                SenseAnchorItem(
                    english_lemma=a.english_lemma,
                    russian_translation=a.russian_translation,
                    relation_type=a.relation_type,
                    score=a.score,
                )
                for a in anchors
            ],
        )

    def register_vocabulary_semantics(
        self,
        *,
        db: Session,
        user_id: int,
        english_lemma: str,
        russian_translation: str,
        context_definition_ru: str | None,
        source_sentence: str | None,
        source_url: str | None,
        vocabulary_item_id: int | None,
    ) -> dict:
        result = self._repo.semantic_upsert(
            db,
            user_id=user_id,
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            context_definition_ru=context_definition_ru,
            source_sentence=source_sentence,
            source_url=source_url,
            vocabulary_item_id=vocabulary_item_id,
        )
        return {
            "sense_id": result.sense.id,
            "semantic_key": result.sense.semantic_key,
            "created_new": result.created_new,
        }

    def register_mistake(
        self,
        *,
        db: Session,
        user_id: int,
        english_lemma: str | None,
        prompt: str | None,
        expected_answer: str | None,
        user_answer: str | None,
    ) -> None:
        self._repo.add_sense_error_event(
            db,
            user_id=user_id,
            english_lemma=english_lemma,
            prompt=prompt,
            expected_answer=expected_answer,
            user_answer=user_answer,
        )

    def delete_vocabulary_links(
        self,
        *,
        db: Session,
        user_id: int,
        vocabulary_item_id: int,
    ) -> int:
        return self._repo.delete_vocabulary_links(
            db,
            user_id=user_id,
            vocabulary_item_id=vocabulary_item_id,
        )

    def list_word_anchors(
        self,
        *,
        db: Session,
        user_id: int,
        english_lemma: str,
        limit: int,
    ) -> list:
        return self._repo.list_anchors(
            db,
            user_id=user_id,
            english_lemma=english_lemma,
            limit=limit,
        )


graph_service = GraphService(graph_repository)
