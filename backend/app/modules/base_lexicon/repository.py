from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.base_lexicon.models import BaseLexiconEntryModel


class BaseLexiconRepository:
    def get_by_lemma(
        self,
        db: Session,
        *,
        english_lemma: str,
    ) -> BaseLexiconEntryModel | None:
        normalized = english_lemma.strip().lower()
        if not normalized:
            return None
        return db.scalar(
            select(BaseLexiconEntryModel).where(
                BaseLexiconEntryModel.english_lemma == normalized,
            )
        )

    def count_entries(self, db: Session) -> int:
        return int(db.scalar(select(func.count(BaseLexiconEntryModel.id))) or 0)

    def seed_defaults(
        self,
        db: Session,
        *,
        entries: list[tuple[str, str]],
    ) -> int:
        created = 0
        for english_lemma, russian_translation in entries:
            normalized = (english_lemma or "").strip().lower()
            translated = (russian_translation or "").strip()
            if not normalized or not translated:
                continue
            if self.get_by_lemma(db, english_lemma=normalized) is not None:
                continue
            db.add(
                BaseLexiconEntryModel(
                    english_lemma=normalized,
                    russian_translation=translated,
                )
            )
            created += 1
        if created:
            db.commit()
        return created

    def upsert_entries(
        self,
        db: Session,
        *,
        entries: list[tuple[str, str]],
    ) -> int:
        updated = 0
        for english_lemma, russian_translation in entries:
            normalized = (english_lemma or "").strip().lower()
            translated = (russian_translation or "").strip()
            if not normalized or not translated:
                continue
            existing = self.get_by_lemma(db, english_lemma=normalized)
            if existing is None:
                db.add(
                    BaseLexiconEntryModel(
                        english_lemma=normalized,
                        russian_translation=translated,
                    )
                )
                updated += 1
                continue
            if existing.russian_translation != translated:
                existing.russian_translation = translated
                db.add(existing)
                updated += 1
        if updated:
            db.commit()
        return updated


base_lexicon_repository = BaseLexiconRepository()
