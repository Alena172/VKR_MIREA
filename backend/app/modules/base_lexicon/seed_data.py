from __future__ import annotations

import json
from pathlib import Path


_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def load_default_base_lexicon_entries() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for path in sorted(_DATA_DIR.glob("base_lexicon*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for item in raw:
            english_lemma = str(item.get("english_lemma", "")).strip().lower()
            russian_translation = str(item.get("russian_translation", "")).strip()
            if not english_lemma or not russian_translation:
                continue
            entries.append((english_lemma, russian_translation))
    return entries
