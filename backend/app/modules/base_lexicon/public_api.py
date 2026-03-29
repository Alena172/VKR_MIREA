from app.modules.base_lexicon.application_service import base_lexicon_application_service


class BaseLexiconPublicApi:
    @staticmethod
    def lookup_translation(
        db,
        *,
        english_lemma: str,
    ) -> str | None:
        return base_lexicon_application_service.lookup_translation(
            db=db,
            english_lemma=english_lemma,
        )

    @staticmethod
    def ensure_seeded(db) -> int:
        return base_lexicon_application_service.ensure_seeded(db=db)

    @staticmethod
    def import_entries(
        db,
        *,
        entries: list[tuple[str, str]],
    ) -> int:
        return base_lexicon_application_service.import_entries(
            db=db,
            entries=entries,
        )


base_lexicon_public_api = BaseLexiconPublicApi()
