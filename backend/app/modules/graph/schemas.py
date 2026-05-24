"""HTTP-модели graph-модуля: интересы и тематические подсказки."""

from pydantic import BaseModel, Field


class InterestItem(BaseModel):
    """Один пользовательский интерес с весом важности."""

    interest: str = Field(min_length=1, max_length=120)
    weight: float = Field(default=1.0, ge=0.1, le=10.0)


class InterestUpsertRequest(BaseModel):
    """Новый набор интересов пользователя для сохранения в графе."""

    interests: list[InterestItem] = Field(default_factory=list, max_length=30)


class UserInterestsResponse(BaseModel):
    """Сохранённые интересы пользователя."""

    user_id: int
    interests: list[InterestItem]



class InterestWordItem(BaseModel):
    """Рекомендованное слово, подобранное по графу интересов."""

    english_lemma: str
    russian_translation: str
    score: float
    reasons: list[str]
    profile_signals: list[str] = Field(default_factory=list)
    primary_signal: str | None = None


class InterestWordsResponse(BaseModel):
    """Список слов, связанных с интересами пользователя."""

    user_id: int
    items: list[InterestWordItem]

