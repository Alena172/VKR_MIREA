from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.ai_services.public_api import ai_service
from app.modules.vocabulary import repository

_GENERIC_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'-]*")
_REUSE_CONFIDENCE_THRESHOLD = 0.72


@dataclass(frozen=True)
class DefinitionResolution:
    """Итог выбора источника контекстного определения."""

    context_definition: str
    source: str
    confidence: str
    reused_from_item_id: int | None = None


def _generic_tokens(text: str | None) -> set[str]:
    return {
        token.lower()
        for token in _GENERIC_TOKEN_RE.findall(text or "")
        if len(token) >= 3
    }


def _classify_confidence(score: float) -> str:
    if score >= 0.9:
        return "high"
    if score >= _REUSE_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def _score_definition_candidate(
    *,
    candidate,
    russian_translation: str,
    source_sentence: str | None,
) -> float:
    score = 0.0

    if candidate.context_definition_ru:
        score += 0.2

    candidate_translation = (candidate.russian_translation or "").strip().lower()
    normalized_translation = russian_translation.strip().lower()
    if candidate_translation and candidate_translation == normalized_translation:
        score += 0.45

    current_tokens = _generic_tokens(source_sentence)
    candidate_tokens = _generic_tokens(candidate.source_sentence)
    if current_tokens and candidate_tokens:
        overlap = len(current_tokens & candidate_tokens) / max(1, len(current_tokens))
        score += 0.35 * overlap
    elif not current_tokens and candidate_translation == normalized_translation:
        score += 0.15

    candidate_source = (candidate.context_definition_source or "").strip().lower()
    if candidate_source.startswith("reuse"):
        score += 0.03
    elif candidate_source.startswith("llm"):
        score += 0.08
    elif candidate_source.startswith("local"):
        score += 0.05

    return min(score, 1.0)


def find_reusable_definition(
    *,
    db: Session,
    user_id: int,
    english_lemma: str,
    russian_translation: str,
    source_sentence: str | None,
) -> DefinitionResolution | None:
    """Находит лучшее сохраненное определение для той же леммы."""

    candidates = repository.list_definition_candidates(
        db,
        user_id=user_id,
        english_lemma=english_lemma,
        limit=20,
    )
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
        source="reuse_existing_context_definition",
        confidence=_classify_confidence(best_score),
        reused_from_item_id=best_candidate.id,
    )


async def resolve_context_definition(
    *,
    db: Session,
    user_id: int,
    english_lemma: str,
    russian_translation: str,
    source_sentence: str | None,
    cefr_level: str | None = None,
) -> DefinitionResolution:
    """Переиспользует подходящее определение или генерирует новое через AI."""

    reusable = find_reusable_definition(
        db=db,
        user_id=user_id,
        english_lemma=english_lemma,
        russian_translation=russian_translation,
        source_sentence=source_sentence,
    )
    if reusable is not None:
        return reusable

    definition = await ai_service.generate_context_definition_async(
        english_lemma=english_lemma,
        russian_translation=russian_translation,
        source_sentence=source_sentence,
        cefr_level=cefr_level,
    )
    return DefinitionResolution(
        context_definition=definition,
        source="llm_generated_context_definition",
        confidence="medium",
        reused_from_item_id=None,
    )
