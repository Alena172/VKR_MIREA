from __future__ import annotations

import json
from pathlib import Path

from app.modules.vocabulary.repository import VocabularyRepository

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


def lookup_translation(*, repo: VocabularyRepository, english_lemma: str) -> str | None:
    entry = repo.get_base_lexicon_entry(english_lemma=english_lemma)
    return entry.russian_translation if entry is not None else None


def ensure_seeded(*, db) -> int:
    from app.modules.vocabulary.repository import VocabularyRepository
    repo = VocabularyRepository(db)
    return repo.seed_default_base_lexicon_entries(
        entries=_load_default_base_lexicon_entries(),
    )


def import_entries(*, repo: VocabularyRepository, entries: list[tuple[str, str]]) -> int:
    return repo.upsert_base_lexicon_entries(entries=entries)
