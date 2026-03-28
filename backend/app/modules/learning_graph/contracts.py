from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationItemDTO:
    english_lemma: str
    russian_translation: str
    topic_cluster: str | None
    score: float
    reasons: list[str]
    strategy_sources: list[str]
    primary_strategy: str | None
    mistake_count: int


@dataclass(frozen=True)
class WordAnchorDTO:
    word_sense_id: int
    english_lemma: str
    russian_translation: str
    semantic_key: str
    relation_type: str
    score: float
    topic_cluster: str | None


@dataclass(frozen=True)
class RegisteredVocabularySenseDTO:
    sense_id: int
    english_lemma: str
    semantic_key: str
    cluster_id: int | None
    created_new_sense: bool
    semantic_duplicate_of_id: int | None
