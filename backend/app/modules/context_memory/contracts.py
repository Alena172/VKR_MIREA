from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WordProgressUpdate:
    word: str
    is_correct: bool
    mark_difficult: bool = False


@dataclass(frozen=True)
class EffectiveCefrDTO:
    cefr_level: str


@dataclass(frozen=True)
class WordProgressTrackingDTO:
    word: str
    tracked: bool


@dataclass(frozen=True)
class LearningProgressUpdateResultDTO:
    difficult_words_added: list[str]


@dataclass(frozen=True)
class MasteredLemmaDTO:
    word: str
