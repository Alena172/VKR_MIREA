from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.core.db import SessionLocal
from app.modules.base_lexicon.public_api import base_lexicon_public_api


def _load_json(path: Path) -> list[tuple[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        (
            str(item.get("english_lemma", "")).strip().lower(),
            str(item.get("russian_translation", "")).strip(),
        )
        for item in raw
        if str(item.get("english_lemma", "")).strip() and str(item.get("russian_translation", "")).strip()
    ]


def _load_csv(path: Path) -> list[tuple[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            (
                str(row.get("english_lemma", "")).strip().lower(),
                str(row.get("russian_translation", "")).strip(),
            )
            for row in reader
            if str(row.get("english_lemma", "")).strip() and str(row.get("russian_translation", "")).strip()
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import entries into base_lexicon.")
    parser.add_argument("file", help="Path to JSON or CSV file.")
    args = parser.parse_args()

    path = Path(args.file).resolve()
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    if path.suffix.lower() == ".json":
        entries = _load_json(path)
    elif path.suffix.lower() == ".csv":
        entries = _load_csv(path)
    else:
        raise SystemExit("Only .json and .csv are supported.")

    db = SessionLocal()
    try:
        changed = base_lexicon_public_api.import_entries(
            db,
            entries=entries,
        )
    finally:
        db.close()

    print(f"Imported or updated {changed} lexicon entries from {path}")


if __name__ == "__main__":
    main()
