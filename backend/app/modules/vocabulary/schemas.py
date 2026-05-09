from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class VocabularyItemCreate(BaseModel):
    """Запрос создания словарной записи для служебного endpoint."""

    user_id: int | None = Field(default=None, ge=1)
    english_lemma: str = Field(min_length=1, max_length=200)
    russian_translation: str = Field(min_length=1, max_length=200)
    context_definition_ru: str | None = Field(default=None, max_length=3000)
    context_definition_source: str | None = Field(default=None, max_length=64)
    context_definition_confidence: str | None = Field(default=None, max_length=16)
    definition_reused_from_item_id: int | None = Field(default=None, ge=1)
    source_sentence: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)


class VocabularyItemCreateMe(BaseModel):
    """Запрос создания словарной записи для текущего пользователя."""

    english_lemma: str = Field(min_length=1, max_length=200)
    russian_translation: str = Field(min_length=1, max_length=200)
    source_sentence: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)


class VocabularyItemRead(BaseModel):
    """Словарная запись в HTTP-ответах."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    english_lemma: str
    russian_translation: str
    context_definition_ru: str | None = None
    context_definition_source: str | None = None
    context_definition_confidence: str | None = None
    definition_reused_from_item_id: int | None = None
    source_sentence: str | None = None
    source_url: str | None = None


class VocabularyItemUpdateMe(BaseModel):
    """Запрос обновления словарной записи текущего пользователя."""

    english_lemma: str = Field(min_length=1, max_length=200)
    russian_translation: str = Field(min_length=1, max_length=200)
    source_sentence: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)


class VocabularyFromCaptureRequest(BaseModel):
    """Запрос сохранения выделенного текста в словарь."""

    user_id: int | None = Field(default=None, ge=1)
    selected_text: str = Field(min_length=1, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)
    source_sentence: str | None = Field(default=None, max_length=5000)
    force_new_vocabulary_item: bool = False


class VocabularyFromCaptureRequestMe(BaseModel):
    """Capture-запрос для текущего пользователя."""

    selected_text: str = Field(min_length=1, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)
    source_sentence: str | None = Field(default=None, max_length=5000)
    force_new_vocabulary_item: bool = False


class VocabularyFromCaptureResponse(BaseModel):
    """Ответ capture-сценария с созданной или найденной записью."""

    vocabulary: VocabularyItemRead


class TranslateRequest(BaseModel):
    """Запрос перевода с возможным указанием пользователя."""

    text: str = Field(min_length=1, max_length=5000)
    user_id: int | None = Field(default=None, ge=1)
    source_context: str | None = Field(default=None, max_length=10000)


class TranslateRequestMe(BaseModel):
    """Запрос перевода для текущего пользователя."""

    text: str = Field(min_length=1, max_length=5000)
    source_context: str | None = Field(default=None, max_length=10000)


class TranslateResponse(BaseModel):
    """Результат перевода и пояснение источника."""

    translated_text: str
    note: str


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

    @staticmethod
    def from_model(item: "VocabularyItemModel") -> "VocabularyItemDTO":
        from app.modules.vocabulary.models import VocabularyItemModel

        if not isinstance(item, VocabularyItemModel):
            raise TypeError("VocabularyItemDTO.from_model expects VocabularyItemModel")

        return VocabularyItemDTO(
            id=item.id,
            user_id=item.user_id,
            english_lemma=item.english_lemma,
            russian_translation=item.russian_translation,
            context_definition_ru=item.context_definition_ru,
            context_definition_source=item.context_definition_source,
            context_definition_confidence=item.context_definition_confidence,
            definition_reused_from_item_id=item.definition_reused_from_item_id,
            source_sentence=item.source_sentence,
            source_url=item.source_url,
        )


@dataclass(frozen=True)
class CaptureDTO:
    """Результат сохранения слова из выделенного текста или контекста."""

    vocabulary: VocabularyItemDTO


@dataclass(frozen=True)
class TranslationResultDTO:
    """Результат перевода вместе с технической заметкой об источнике."""

    translated_text: str
    note: str
