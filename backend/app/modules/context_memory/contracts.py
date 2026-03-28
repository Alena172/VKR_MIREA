from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WordProgressUpdate:
    word: str
    is_correct: bool
    mark_difficult: bool = False
