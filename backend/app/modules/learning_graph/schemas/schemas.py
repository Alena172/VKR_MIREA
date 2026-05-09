from pydantic import BaseModel, Field


class InterestItem(BaseModel):
    """Один интерес пользователя в HTTP API."""

    interest: str = Field(min_length=1, max_length=120)
    weight: float = Field(default=1.0, ge=0.1, le=10.0)


class InterestUpsertRequest(BaseModel):
    """Запрос ручного обновления интересов пользователя."""

    interests: list[InterestItem] = Field(default_factory=list, max_length=30)


class UserInterestsResponse(BaseModel):
    user_id: int
    interests: list[InterestItem]


class SemanticUpsertRequest(BaseModel):
    """Запрос регистрации смысла слова в learning graph."""

    english_lemma: str = Field(min_length=1, max_length=200)
    russian_translation: str = Field(min_length=1, max_length=200)
    context_definition_ru: str | None = Field(default=None, max_length=3000)
    source_sentence: str | None = Field(default=None, max_length=5000)
    source_url: str | None = Field(default=None, max_length=2000)
    topic_hint: str | None = Field(default=None, max_length=120)
    vocabulary_item_id: int | None = Field(default=None, ge=1)


class WordSenseRead(BaseModel):
    """Смысл слова в HTTP-ответах."""

    id: int
    english_lemma: str
    semantic_key: str
    russian_translation: str


class SemanticUpsertResponse(BaseModel):
    user_id: int
    created_new_sense: bool
    sense: WordSenseRead


class InterestWordItem(BaseModel):
    """Слово, связанное с интересами пользователя."""

    english_lemma: str
    russian_translation: str
    score: float
    reasons: list[str]
    profile_signals: list[str] = Field(default_factory=list)
    primary_signal: str | None = None


class InterestWordsResponse(BaseModel):
    user_id: int
    items: list[InterestWordItem]


class SenseAnchorItem(BaseModel):
    """Связанное слово и тип семантической связи."""

    english_lemma: str
    russian_translation: str
    relation_type: str
    score: float


class SenseAnchorsResponse(BaseModel):
    user_id: int
    english_lemma: str
    anchors: list[SenseAnchorItem]
