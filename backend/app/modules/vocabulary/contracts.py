from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VocabularyItemDTO:
    """Словарная запись, которую vocabulary отдает наружу."""

    id: int
    user_id: int
    english_lemma: str
    russian_translation: str
    context_definition_ru: str | None
    context_definition_source: str | None
    context_definition_confidence: str | None
    definition_reused_from_item_id: int | None
    source_sentence: str | None
    source_url: str | None


@dataclass(frozen=True)
class VocabularyFromCaptureResultDTO:
    """Результат сохранения слова из выделенного текста или контекста."""

    vocabulary: VocabularyItemDTO


@dataclass(frozen=True)
class TranslationResultDTO:
    """Результат перевода вместе с технической заметкой об источнике."""

    translated_text: str
    note: str
