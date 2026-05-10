from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field


class DictionaryEntryCreate(BaseModel):
    english_lemma: str = Field(min_length=1, max_length=200)
    russian_translation: str = Field(min_length=1, max_length=200)
    context_definition_ru: str | None = Field(default=None, max_length=3000)


class VocabularyItemCreate(BaseModel):
    """Запрос создания словарной записи (служебный endpoint)."""

    user_id: int | None = Field(default=None, ge=1)
    english_lemma: str = Field(min_length=1, max_length=200)
    russian_translation: str = Field(min_length=1, max_length=200)
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

    id: int
    user_id: int
    english_lemma: str
    russian_translation: str
    context_definition_ru: str | None = None
    source_sentence: str | None = None
    source_url: str | None = None
    added_at: datetime
    is_phrase: bool = False


class VocabularyItemUpdateMe(BaseModel):
    """Запрос обновления контекста словарной записи пользователя."""

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
    """Запрос capture-сценария для текущего пользователя."""

    selected_text: str = Field(min_length=1, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)
    source_sentence: str | None = Field(default=None, max_length=5000)
    force_new_vocabulary_item: bool = False


class VocabularyFromCaptureResponse(BaseModel):
    """Ответ capture-сценария с созданной или найденной записью."""

    vocabulary: VocabularyItemRead
    created_new_vocabulary_item: bool = False


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    user_id: int | None = Field(default=None, ge=1)
    source_context: str | None = Field(default=None, max_length=10000)


class TranslateRequestMe(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    source_context: str | None = Field(default=None, max_length=10000)


class TranslateResponse(BaseModel):
    translated_text: str
    note: str


@dataclass(frozen=True)
class VocabularyItemDTO:
    """Словарная запись, которую vocabulary отдаёт наружу."""

    id: int
    user_id: int
    english_lemma: str
    russian_translation: str
    context_definition_ru: str | None
    source_sentence: str | None
    source_url: str | None
    added_at: datetime
    is_phrase: bool = False

    @staticmethod
    def from_model(uv: UserVocabularyModel, entry: DictionaryEntryModel | None) -> VocabularyItemDTO:
        if entry is None:
            # Фраза: данные хранятся прямо в `user_vocabulary`.
            return VocabularyItemDTO(
                id=uv.id,
                user_id=uv.user_id,
                english_lemma=uv.phrase_en or "",
                russian_translation=uv.phrase_ru or "",
                context_definition_ru=None,
                source_sentence=uv.source_sentence,
                source_url=uv.source_url,
                added_at=uv.added_at,
                is_phrase=True,
            )
        return VocabularyItemDTO(
            id=uv.id,
            user_id=uv.user_id,
            english_lemma=entry.english_lemma,
            russian_translation=entry.russian_translation,
            context_definition_ru=entry.context_definition_ru,
            source_sentence=uv.source_sentence,
            source_url=uv.source_url,
            added_at=uv.added_at,
            is_phrase=False,
        )


@dataclass(frozen=True)
class CaptureDTO:
    """Результат сохранения слова из выделенного текста."""

    vocabulary: VocabularyItemDTO


@dataclass(frozen=True)
class TranslationResultDTO:
    """Результат перевода вместе с технической заметкой об источнике."""

    translated_text: str
    note: str
