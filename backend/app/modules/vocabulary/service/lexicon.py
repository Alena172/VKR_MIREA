from __future__ import annotations

from app.modules.vocabulary.repository import VocabularyRepository


def lookup_translation(*, repo: VocabularyRepository, english_lemma: str) -> str | None:
    """Быстрый поиск перевода в общем словаре dictionary_entries без AI."""
    return repo.find_shared_translation(english_lemma=english_lemma)
