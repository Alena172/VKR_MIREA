from __future__ import annotations

from app.modules.vocabulary.assembler import to_vocabulary_item_dto
from app.modules.vocabulary.contracts import VocabularyItemDTO
from app.modules.vocabulary.repository import vocabulary_repository

__all__ = [
    "VocabularyItemDTO",
    "vocabulary_public_api",
]


class VocabularyPublicApi:
    get_translation_map = staticmethod(vocabulary_repository.get_translation_map)
    get_definition_map = staticmethod(vocabulary_repository.get_definition_map)
    list_english_lemmas = staticmethod(vocabulary_repository.list_english_lemmas)

    @staticmethod
    def list_items(db, user_id: int | None) -> list[VocabularyItemDTO]:
        return [to_vocabulary_item_dto(item) for item in vocabulary_repository.list_items(db, user_id=user_id)]

    @staticmethod
    def get_latest_by_lemma(db, user_id: int, english_lemma: str) -> VocabularyItemDTO | None:
        item = vocabulary_repository.get_latest_by_lemma(
            db,
            user_id=user_id,
            english_lemma=english_lemma,
        )
        return to_vocabulary_item_dto(item) if item is not None else None


vocabulary_public_api = VocabularyPublicApi()
