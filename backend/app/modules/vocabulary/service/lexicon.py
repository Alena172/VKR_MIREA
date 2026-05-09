from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.modules.vocabulary import repository

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _load_default_base_lexicon_entries() -> list[tuple[str, str]]:
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


def lookup_translation(
    *,
    db: Session,
    english_lemma: str,
) -> str | None:
    entry = repository.get_base_lexicon_entry(
        db,
        english_lemma=english_lemma,
    )
    return entry.russian_translation if entry is not None else None


def ensure_seeded(*, db: Session) -> int:
    return repository.seed_default_base_lexicon_entries(
        db,
        entries=_load_default_base_lexicon_entries(),
    )


def import_entries(
    *,
    db: Session,
    entries: list[tuple[str, str]],
) -> int:
    return repository.upsert_base_lexicon_entries(
        db,
        entries=entries,
    )
