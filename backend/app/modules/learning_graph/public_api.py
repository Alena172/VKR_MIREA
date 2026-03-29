from __future__ import annotations

from app.modules.learning_graph.assembler import (
    to_recommendation_item_dto,
    to_word_anchor_dto,
)
from app.modules.learning_graph.contracts import (
    RecommendationItemDTO,
    RegisteredVocabularySenseDTO,
    WordAnchorDTO,
)
from app.modules.learning_graph.application_service import learning_graph_application_service

__all__ = [
    "RecommendationItemDTO",
    "RegisteredVocabularySenseDTO",
    "WordAnchorDTO",
    "learning_graph_public_api",
]


class LearningGraphPublicApi:
    register_mistake = staticmethod(learning_graph_application_service.register_mistake)

    @staticmethod
    def list_recommendation_items(
        db,
        *,
        user_id: int,
        mode: str,
        limit: int,
    ) -> list[RecommendationItemDTO]:
        items = learning_graph_application_service.list_recommendation_items(
            db=db,
            user_id=user_id,
            mode=mode,
            limit=limit,
        )
        return [to_recommendation_item_dto(item) for item in items]

    @staticmethod
    def register_vocabulary_semantics(
        db,
        *,
        user_id: int,
        english_lemma: str,
        russian_translation: str,
        context_definition_ru: str | None,
        source_sentence: str | None,
        source_url: str | None,
        vocabulary_item_id: int | None,
    ) -> RegisteredVocabularySenseDTO:
        return learning_graph_application_service.register_vocabulary_semantics(
            db=db,
            user_id=user_id,
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            context_definition_ru=context_definition_ru,
            source_sentence=source_sentence,
            source_url=source_url,
            vocabulary_item_id=vocabulary_item_id,
        )

    @staticmethod
    def list_word_anchors(
        db,
        *,
        user_id: int,
        english_lemma: str,
        limit: int,
    ) -> list[WordAnchorDTO]:
        items = learning_graph_application_service.list_word_anchors(
            db=db,
            user_id=user_id,
            english_lemma=english_lemma,
            limit=limit,
        )
        return [to_word_anchor_dto(item) for item in items]

    @staticmethod
    def delete_vocabulary_links(
        db,
        *,
        user_id: int,
        vocabulary_item_id: int,
    ) -> int:
        return learning_graph_application_service.delete_vocabulary_links(
            db=db,
            user_id=user_id,
            vocabulary_item_id=vocabulary_item_id,
        )


learning_graph_public_api = LearningGraphPublicApi()
