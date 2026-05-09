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


class VocabularyItem(BaseModel):
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

    vocabulary: VocabularyItem
