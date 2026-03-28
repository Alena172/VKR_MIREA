from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureItemDTO:
    id: int
    user_id: int
    selected_text: str
    source_url: str | None
    source_sentence: str | None
