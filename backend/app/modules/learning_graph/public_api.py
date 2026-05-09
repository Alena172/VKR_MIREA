from __future__ import annotations

from app.modules.learning_graph.assemblers import (
    to_word_anchor_dto,
)
from app.modules.learning_graph.contracts import (
    RegisteredVocabularySenseDTO,
    WordAnchorDTO,
)
from app.modules.learning_graph.services.service import learning_graph_application_service

__all__ = [
    "RegisteredVocabularySenseDTO",
    "WordAnchorDTO",
    "learning_graph_public_api",
]


class LearningGraphPublicApi:
    """Публичный фасад learning_graph для vocabulary и learning."""

    register_mistake = staticmethod(learning_graph_application_service.register_mistake)

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
        """Регистрирует смысл словарной записи без раскрытия внутреннего сервиса."""

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
        """Возвращает связанные слова как DTO для генерации упражнений."""

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
        """Удаляет связи словарной записи при удалении vocabulary item."""

        return learning_graph_application_service.delete_vocabulary_links(
            db=db,
            user_id=user_id,
            vocabulary_item_id=vocabulary_item_id,
        )


learning_graph_public_api = LearningGraphPublicApi()
