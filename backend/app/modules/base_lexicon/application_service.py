from sqlalchemy.orm import Session

from app.modules.base_lexicon.repository import base_lexicon_repository
from app.modules.base_lexicon.seed_data import load_default_base_lexicon_entries


class BaseLexiconApplicationService:
    def lookup_translation(
        self,
        *,
        db: Session,
        english_lemma: str,
    ) -> str | None:
        entry = base_lexicon_repository.get_by_lemma(
            db,
            english_lemma=english_lemma,
        )
        return entry.russian_translation if entry is not None else None

    def ensure_seeded(
        self,
        *,
        db: Session,
    ) -> int:
        return base_lexicon_repository.seed_defaults(
            db,
            entries=load_default_base_lexicon_entries(),
        )

    def import_entries(
        self,
        *,
        db: Session,
        entries: list[tuple[str, str]],
    ) -> int:
        return base_lexicon_repository.upsert_entries(
            db,
            entries=entries,
        )


base_lexicon_application_service = BaseLexiconApplicationService()
