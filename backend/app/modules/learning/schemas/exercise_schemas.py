from pydantic import BaseModel, Field


class ExerciseGenerateRequest(BaseModel):
    """Запрос генерации упражнений для служебного endpoint."""

    user_id: int | None = Field(default=None, ge=1)
    vocabulary_ids: list[int] = Field(default_factory=list)
    size: int = Field(default=10, ge=1, le=30)
    fast_start: bool = False
    incremental: bool = False
    mode: str = Field(
        default="sentence_translation_full",
        pattern="^(sentence_translation_full|word_definition_match|word_scramble)$",
    )


class ExerciseGenerateRequestMe(BaseModel):
    """Запрос генерации упражнений для текущего пользователя."""

    vocabulary_ids: list[int] = Field(default_factory=list)
    size: int = Field(default=10, ge=1, le=30)
    fast_start: bool = False
    incremental: bool = False
    mode: str = Field(
        default="sentence_translation_full",
        pattern="^(sentence_translation_full|word_definition_match|word_scramble)$",
    )


class ExerciseItem(BaseModel):
    """Упражнение, которое frontend показывает пользователю."""

    prompt: str
    answer: str
    exercise_type: str
    target_word: str | None = None
    options: list[str] = Field(default_factory=list)


class ExerciseGenerateResponse(BaseModel):
    """Ответ синхронной генерации упражнений."""

    exercises: list[ExerciseItem]
    note: str
