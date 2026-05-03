from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InterestItemDTO:
    interest: str
    weight: float


@dataclass(frozen=True)
class InterestWordItemDTO:
    english_lemma: str
    russian_translation: str
    score: float
    reasons: list[str]
    profile_signals: list[str]
    primary_signal: str | None


@dataclass(frozen=True)
class WordAnchorDTO:
    english_lemma: str
    russian_translation: str
    relation_type: str
    score: float


@dataclass(frozen=True)
class RegisteredVocabularySenseDTO:
    sense_id: int
    english_lemma: str
    semantic_key: str
    cluster_id: int | None
    created_new_sense: bool
    semantic_duplicate_of_id: int | None


@dataclass(frozen=True)
class UserInterestsDTO:
    user_id: int
    interests: list[InterestItemDTO]


@dataclass(frozen=True)
class WordSenseDTO:
    id: int
    english_lemma: str
    semantic_key: str
    russian_translation: str


@dataclass(frozen=True)
class SemanticUpsertResultDTO:
    user_id: int
    created_new_sense: bool
    sense: WordSenseDTO


@dataclass(frozen=True)
class InterestWordsDTO:
    user_id: int
    mode: str
    items: list[InterestWordItemDTO]


@dataclass(frozen=True)
class SenseAnchorsDTO:
    user_id: int
    english_lemma: str
    anchors: list[WordAnchorDTO]
