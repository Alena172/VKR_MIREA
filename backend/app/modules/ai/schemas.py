from pydantic import BaseModel, Field


class TranslateGlossaryItem(BaseModel):
    """Подсказка перевода для термина, уже известного системе."""

    english_term: str = Field(min_length=1, max_length=200)
    russian_translation: str = Field(min_length=1, max_length=200)
    source_sentence: str | None = Field(default=None, max_length=2000)


class TranslateWithContextRequest(BaseModel):
    """Запрос перевода текста с учетом уровня и контекста."""

    text: str = Field(min_length=1, max_length=5000)
    cefr_level: str | None = Field(default=None, pattern="^(A1|A2|B1|B2|C1|C2)$")
    source_context: str | None = Field(default=None, max_length=10000)
    glossary: list[TranslateGlossaryItem] = Field(default_factory=list)
    force_ai: bool = Field(default=False)


class TranslateWithContextResponse(BaseModel):
    """Ответ перевода и заметка о провайдере или fallback-сценарии."""

    translated_text: str
    provider_note: str


class ExerciseSeed(BaseModel):
    """Исходные данные словарной записи для генерации упражнения."""

    english_lemma: str = Field(min_length=1, max_length=200)
    russian_translation: str = Field(min_length=1, max_length=200)
    context_definition_ru: str | None = Field(default=None, max_length=4000)
    source_sentence: str | None = Field(default=None, max_length=2000)
    topic_cluster_key: str | None = Field(default=None, max_length=64)
    cluster_word_hint: str | None = Field(default=None, max_length=200)


class GenerateExercisesRequest(BaseModel):
    """Запрос генерации упражнений по набору seed-слов."""

    size: int = Field(ge=1, le=30)
    cefr_level: str | None = Field(default=None, pattern="^(A1|A2|B1|B2|C1|C2)$")
    fast_start: bool = False
    mode: str = Field(
        default="sentence_translation_full",
        pattern="^(sentence_translation_full|word_definition_match|word_scramble)$",
    )
    seeds: list[ExerciseSeed] = Field(default_factory=list)


class GeneratedExerciseItem(BaseModel):
    """Одно упражнение, сгенерированное AI-сервисом."""

    prompt: str
    answer: str
    exercise_type: str
    target_word: str | None = Field(default=None, max_length=200)
    options: list[str] = Field(default_factory=list)


class GenerateExercisesResponse(BaseModel):
    """Ответ генератора упражнений."""

    exercises: list[GeneratedExerciseItem]
    provider_note: str


class AIStatusResponse(BaseModel):
    """Текущая конфигурация Ollama для диагностики."""

    model: str
    remote_enabled: bool
    base_url: str
    timeout_seconds: float
    max_retries: int
