from __future__ import annotations

from app.modules.vocabulary.repository import vocabulary_repository

__all__ = [
    "vocabulary_public_api",
]


class VocabularyPublicApi:
    list_items = staticmethod(vocabulary_repository.list_items)
    get_translation_map = staticmethod(vocabulary_repository.get_translation_map)
    get_definition_map = staticmethod(vocabulary_repository.get_definition_map)
    get_latest_by_lemma = staticmethod(vocabulary_repository.get_latest_by_lemma)
    list_english_lemmas = staticmethod(vocabulary_repository.list_english_lemmas)


vocabulary_public_api = VocabularyPublicApi()
