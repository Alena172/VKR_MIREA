from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InterestItemDTO:
    """Один интерес пользователя в семантическом профиле."""

    interest: str
    weight: float


@dataclass(frozen=True)
class InterestWordItemDTO:
    """Слово, связанное с интересами или сигналами профиля."""

    english_lemma: str
    russian_translation: str
    score: float
    reasons: list[str]
    profile_signals: list[str]
    primary_signal: str | None


@dataclass(frozen=True)
class WordAnchorDTO:
    """Смысловой якорь: связанное слово и тип связи."""

    english_lemma: str
    russian_translation: str
    relation_type: str
    score: float


@dataclass(frozen=True)
class RegisteredVocabularySenseDTO:
    """Результат привязки словарной записи к смыслу слова."""

    sense_id: int
    english_lemma: str
    semantic_key: str
    cluster_id: int | None
    created_new_sense: bool
    semantic_duplicate_of_id: int | None


@dataclass(frozen=True)
class UserInterestsDTO:
    """Список интересов пользователя."""

    user_id: int
    interests: list[InterestItemDTO]


@dataclass(frozen=True)
class WordSenseDTO:
    """Конкретный смысл английской леммы."""

    id: int
    english_lemma: str
    semantic_key: str
    russian_translation: str


@dataclass(frozen=True)
class SemanticUpsertResultDTO:
    """Результат создания или переиспользования смысла слова."""

    user_id: int
    created_new_sense: bool
    sense: WordSenseDTO


@dataclass(frozen=True)
class InterestWordsDTO:
    """Слова, подобранные по интересам или семантическим сигналам."""

    user_id: int
    mode: str
    items: list[InterestWordItemDTO]


@dataclass(frozen=True)
class SenseAnchorsDTO:
    """Смысловые связи для одной английской леммы."""

    user_id: int
    english_lemma: str
    anchors: list[WordAnchorDTO]
