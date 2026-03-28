from __future__ import annotations

from app.modules.vocabulary.contracts import VocabularyItemDTO
from app.modules.vocabulary.models import VocabularyItemModel


def to_vocabulary_item_dto(item: VocabularyItemModel) -> VocabularyItemDTO:
    return VocabularyItemDTO(
        id=item.id,
        user_id=item.user_id,
        english_lemma=item.english_lemma,
        russian_translation=item.russian_translation,
        context_definition_ru=item.context_definition_ru,
        source_sentence=item.source_sentence,
        source_url=item.source_url,
    )
