from pydantic import BaseModel, Field


class InterestItem(BaseModel):
    interest: str = Field(min_length=1, max_length=120)
    weight: float = Field(default=1.0, ge=0.1, le=10.0)


class InterestUpsertRequest(BaseModel):
    interests: list[InterestItem] = Field(default_factory=list, max_length=30)


class UserInterestsResponse(BaseModel):
    user_id: int
    interests: list[InterestItem]



class InterestWordItem(BaseModel):
    english_lemma: str
    russian_translation: str
    score: float
    reasons: list[str]
    profile_signals: list[str] = Field(default_factory=list)
    primary_signal: str | None = None


class InterestWordsResponse(BaseModel):
    user_id: int
    items: list[InterestWordItem]


