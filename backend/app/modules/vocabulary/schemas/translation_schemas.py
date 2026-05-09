from pydantic import BaseModel, Field


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
