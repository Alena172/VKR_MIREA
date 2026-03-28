from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.application import application_access, application_transaction
from app.modules.context_memory.public_api import context_memory_public_api
from app.modules.learning_graph.assembler import to_registered_vocabulary_sense_dto
from app.modules.learning_graph.contracts import RegisteredVocabularySenseDTO
from app.modules.learning_graph.repository import learning_graph_repository
from app.modules.learning_graph.schemas import (
    InterestUpsertRequest,
    LearningGraphObservabilityResponse,
    LearningGraphOverviewResponse,
    RecommendationsResponse,
    SemanticUpsertRequest,
    SemanticUpsertResponse,
    SenseAnchorsResponse,
    TopicClusterRead,
    UserInterestsResponse,
    WordSenseRead,
)


class LearningGraphApplicationService:
    def get_overview(
        self,
        *,
        db: Session,
        current_user_id: int,
    ) -> LearningGraphOverviewResponse:
        application_access.ensure_user_exists(db=db, user_id=current_user_id)
        overview = learning_graph_repository.get_overview(db, user_id=current_user_id)
        return LearningGraphOverviewResponse(user_id=current_user_id, **overview)

    def list_interests(
        self,
        *,
        db: Session,
        current_user_id: int,
    ) -> UserInterestsResponse:
        application_access.ensure_user_exists(db=db, user_id=current_user_id)
        return UserInterestsResponse(
            user_id=current_user_id,
            interests=learning_graph_repository.list_interests(db, current_user_id),
        )

    def upsert_interests(
        self,
        *,
        db: Session,
        payload: InterestUpsertRequest,
        current_user_id: int,
    ) -> UserInterestsResponse:
        application_access.ensure_user_exists(db=db, user_id=current_user_id)
        updated = learning_graph_repository.upsert_interests(
            db,
            user_id=current_user_id,
            interests=payload.interests,
        )
        return UserInterestsResponse(user_id=current_user_id, interests=updated)

    def semantic_upsert(
        self,
        *,
        db: Session,
        payload: SemanticUpsertRequest,
        current_user_id: int,
    ) -> SemanticUpsertResponse:
        application_access.ensure_user_exists(db=db, user_id=current_user_id)

        try:
            with application_transaction.boundary(db=db):
                result = learning_graph_repository.semantic_upsert(
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

        cluster_read = None
        if result.cluster is not None:
            cluster_read = TopicClusterRead(
                id=result.cluster.id,
                key=result.cluster.cluster_key,
                name=result.cluster.name,
                description=result.cluster.description,
            )

        return SemanticUpsertResponse(
            user_id=current_user_id,
            created_new_sense=result.created_new,
            semantic_duplicate_of_id=result.duplicate_of_id,
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
            cluster=cluster_read,
        )

    def get_recommendations(
        self,
        *,
        db: Session,
        mode: str,
        limit: int,
        current_user_id: int,
    ) -> RecommendationsResponse:
        application_access.ensure_user_exists(db=db, user_id=current_user_id)
        known_lemmas = context_memory_public_api.list_mastered_lemmas(
            db=db,
            user_id=current_user_id,
        )
        items = learning_graph_repository.get_recommendations(
            db,
            user_id=current_user_id,
            mode=mode,
            limit=limit,
            known_lemmas=known_lemmas,
        )
        return RecommendationsResponse(user_id=current_user_id, mode=mode, items=items)

    def list_recommendation_items(
        self,
        *,
        db: Session,
        user_id: int,
        mode: str,
        limit: int,
    ):
        known_lemmas = context_memory_public_api.list_mastered_lemmas(
            db=db,
            user_id=user_id,
        )
        return learning_graph_repository.get_recommendations(
            db,
            user_id=user_id,
            mode=mode,
            limit=limit,
            known_lemmas=known_lemmas,
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
    ) -> RegisteredVocabularySenseDTO:
        result = learning_graph_repository.semantic_upsert(
            db,
            user_id=user_id,
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            context_definition_ru=context_definition_ru,
            source_sentence=source_sentence,
            source_url=source_url,
            vocabulary_item_id=vocabulary_item_id,
        )
        return to_registered_vocabulary_sense_dto(result)

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
        learning_graph_repository.add_mistake_event(
            db,
            user_id=user_id,
            english_lemma=english_lemma,
            prompt=prompt,
            expected_answer=expected_answer,
            user_answer=user_answer,
        )

    def list_word_anchors(
        self,
        *,
        db: Session,
        user_id: int,
        english_lemma: str,
        limit: int,
    ):
        return learning_graph_repository.list_anchors(
            db,
            user_id=user_id,
            english_lemma=english_lemma,
            limit=limit,
        )

    def get_observability(
        self,
        *,
        db: Session,
        current_user_id: int,
    ) -> LearningGraphObservabilityResponse:
        application_access.ensure_user_exists(db=db, user_id=current_user_id)
        snapshot = learning_graph_repository.get_observability(user_id=current_user_id)
        return LearningGraphObservabilityResponse(user_id=current_user_id, **snapshot)

    def get_anchors(
        self,
        *,
        db: Session,
        english_lemma: str,
        limit: int,
        current_user_id: int,
    ) -> SenseAnchorsResponse:
        application_access.ensure_user_exists(db=db, user_id=current_user_id)
        anchors = learning_graph_repository.list_anchors(
            db,
            user_id=current_user_id,
            english_lemma=english_lemma,
            limit=limit,
        )
        return SenseAnchorsResponse(
            user_id=current_user_id,
            english_lemma=english_lemma.strip().lower(),
            anchors=anchors,
        )


learning_graph_application_service = LearningGraphApplicationService()
