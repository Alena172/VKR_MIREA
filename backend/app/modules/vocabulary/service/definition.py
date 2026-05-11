from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.ai.facade import ai_facade as ai_service
from app.modules.ai.free_dictionary_client import lookup_definition
from app.modules.vocabulary.repository import VocabularyRepository

_GENERIC_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'-]*")
_REUSE_CONFIDENCE_THRESHOLD = 0.72


@dataclass(frozen=True)
class DefinitionResolution:
    context_definition: str | None
    source: str
    confidence: str


def _generic_tokens(text: str | None) -> set[str]:
    return {token.lower() for token in _GENERIC_TOKEN_RE.findall(text or "") if len(token) >= 3}


def _classify_confidence(score: float) -> str:
    if score >= 0.9:
        return "high"
    if score >= _REUSE_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def _score_definition_candidate(*, candidate, russian_translation: str, source_sentence: str | None) -> float:
    score = 0.0
    if candidate.context_definition_ru:
        score += 0.2
    candidate_translation = (candidate.russian_translation or "").strip().lower()
    normalized_translation = russian_translation.strip().lower()
    if candidate_translation and candidate_translation == normalized_translation:
        score += 0.45
    current_tokens = _generic_tokens(source_sentence)
    candidate_tokens = _generic_tokens(getattr(candidate, "source_sentence", None))
    if current_tokens and candidate_tokens:
        overlap = len(current_tokens & candidate_tokens) / max(1, len(current_tokens))
        score += 0.35 * overlap
    elif not current_tokens and candidate_translation == normalized_translation:
        score += 0.15
    return min(score, 1.0)


def find_reusable_definition(
    *,
    repo: VocabularyRepository,
    english_lemma: str,
    russian_translation: str,
    source_sentence: str | None,
) -> DefinitionResolution | None:
    candidates = repo.list_definition_candidates(english_lemma=english_lemma)
    best_candidate = None
    best_score = 0.0
    for candidate in candidates:
        score = _score_definition_candidate(
            candidate=candidate,
            russian_translation=russian_translation,
            source_sentence=source_sentence,
        )
        if score > best_score:
            best_score = score
            best_candidate = candidate

    if best_candidate is None or best_score < _REUSE_CONFIDENCE_THRESHOLD:
        return None

    return DefinitionResolution(
        context_definition=best_candidate.context_definition_ru or "",
        source="reuse_dictionary_definition",
        confidence=_classify_confidence(best_score),
    )


async def resolve_context_definition(
    *,
    repo: VocabularyRepository,
    english_lemma: str,
    russian_translation: str,
    source_sentence: str | None,
    cefr_level: str | None = None,
) -> DefinitionResolution:
    # Фразы (несколько слов) — определение не генерируем
    if " " in english_lemma.strip():
        return DefinitionResolution(context_definition=None, source="skipped_phrase", confidence="high")

    # 1. Переиспользуем уже сохранённое определение из БД
    reusable = find_reusable_definition(
        repo=repo,
        english_lemma=english_lemma,
        russian_translation=russian_translation,
        source_sentence=source_sentence,
    )
    if reusable is not None:
        return reusable

    # 2. Free Dictionary API (бесплатно, без токенов)
    dict_result = await lookup_definition(
        english_lemma,
        russian_translation=russian_translation,
        source_sentence=source_sentence,
    )
    if dict_result is not None:
        return DefinitionResolution(
            context_definition=dict_result.definition,
            source="free_dictionary_api",
            confidence=_classify_confidence(dict_result.score),
        )

    # 3. AI — для многозначных слов с низким score и редких слов
    definition = await ai_service.generate_context_definition_async(
        english_lemma=english_lemma,
        russian_translation=russian_translation,
        source_sentence=source_sentence,
        cefr_level=cefr_level,
    )
    return DefinitionResolution(
        context_definition=definition,
        source="llm_generated",
        confidence="medium",
    )
