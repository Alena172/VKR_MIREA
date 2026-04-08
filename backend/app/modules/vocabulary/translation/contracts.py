from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationResultDTO:
    translated_text: str
    note: str
