from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.application import application_access, application_transaction
from app.modules.ai.schemas import TranslateWithContextRequest
from app.modules.ai.facade import ai_facade as ai_service
from app.modules.review.service.srs import srs_service as context_memory_public_api
from app.modules.graph.service.graph import graph_service as learning_graph_public_api
from app.modules.vocabulary import repository
from app.modules.vocabulary.models import CaptureModel
from app.modules.vocabulary.schemas import CaptureDTO, VocabularyItemCreate, VocabularyItemDTO
from app.modules.vocabulary.service.definition import resolve_context_definition
from app.modules.vocabulary.service.lexicon import lookup_translation

_ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_RUSSIAN_TOKEN_RE = re.compile(r"[А-Яа-яЁё-]+")


def _to_capture_dto(item) -> CaptureDTO:
    return CaptureDTO(vocabulary=VocabularyItemDTO.from_model(item))


def _normalize_english_lemma(text: str) -> str:
    return text.strip().split()[0].lower()


def _normalize_translation(text: str) -> str:
    value = text.strip()
    if value.startswith("[RU]"):
        value = value.replace("[RU]", "", 1).strip()
    return value or "перевод не найден"


def _english_tokens(text: str | None) -> list[str]:
    return [token.lower() for token in _ENGLISH_TOKEN_RE.findall(text or "")]


def _russian_tokens(text: str | None) -> list[str]:
    return [token.lower() for token in _RUSSIAN_TOKEN_RE.findall(text or "")]


def _is_single_word_capture(text: str) -> bool:
    return len(_english_tokens(text)) == 1


def _looks_like_context_phrase_expansion(
    *,
    base_translation: str,
    contextual_translation: str,
) -> bool:
    base_tokens = _russian_tokens(base_translation)
    contextual_tokens = _russian_tokens(contextual_translation)
    if not base_tokens or not contextual_tokens:
        return False
    if base_tokens == contextual_tokens:
        return False
    if len(base_tokens) == 1 and len(contextual_tokens) >= 2:
        return True
    return False


async def _generate_capture_ai_data(
    *,
    capture: CaptureModel,
    english_lemma: str,
    cefr_level: str,
    db: Session,
) -> tuple[str, str, str | None]:
    if _is_single_word_capture(capture.selected_text):
        fast_translation = lookup_translation(
            db=db,
            english_lemma=english_lemma,
        ) or ai_service.fast_translate_single_word(english_lemma)
        if fast_translation:
            normalized_fast_translation = _normalize_translation(fast_translation)
            return (
                normalized_fast_translation,
                "fast_local_word_translation; local_definition",
                None,
            )

    contextual_response = await ai_service.translate_with_context_async(
        TranslateWithContextRequest(
            text=english_lemma,
            cefr_level=cefr_level,
            source_context=capture.source_sentence,
        )
    )
    contextual_translation = _normalize_translation(contextual_response.translated_text)

    translation_note = contextual_response.provider_note
    semantic_sentence = capture.source_sentence
    russian_translation = contextual_translation

    if _is_single_word_capture(capture.selected_text):
        base_response = await ai_service.translate_with_context_async(
            TranslateWithContextRequest(
                text=english_lemma,
                cefr_level=cefr_level,
                source_context=None,
            )
        )
        base_translation = _normalize_translation(base_response.translated_text)

        if _looks_like_context_phrase_expansion(
            base_translation=base_translation,
            contextual_translation=contextual_translation,
        ):
            russian_translation = base_translation
            semantic_sentence = None
            translation_note = (
                f"{contextual_response.provider_note}; "
                "capture_mode=base_word_translation; "
                f"context_variant_ignored={contextual_translation}"
            )
        else:
            russian_translation = contextual_translation or base_translation
            translation_note = (
                f"{contextual_response.provider_note}; "
                "capture_mode=contextual_single_word"
            )

    return russian_translation, translation_note, semantic_sentence


async def capture_to_vocabulary(
    *,
    db: Session,
    user_id: int,
    selected_text: str,
    source_url: str | None,
    source_sentence: str | None,
    force_new_vocabulary_item: bool,
) -> CaptureDTO:
    user = application_access.get_user_or_404(db=db, user_id=user_id)
    capture = CaptureModel(
        user_id=user_id,
        selected_text=selected_text,
        source_url=source_url.strip() if source_url else None,
        source_sentence=source_sentence.strip() if source_sentence else None,
        force_new_vocabulary_item=force_new_vocabulary_item,
    )
    english_lemma = _normalize_english_lemma(capture.selected_text)

    russian_translation, _translation_note, semantic_sentence = await _generate_capture_ai_data(
        capture=capture,
        english_lemma=english_lemma,
        cefr_level=user.cefr_level,
        db=db,
    )
    definition_resolution = await resolve_context_definition(
        db=db,
        user_id=user_id,
        english_lemma=english_lemma,
        russian_translation=russian_translation,
        source_sentence=semantic_sentence,
    )

    with application_transaction.boundary(db=db):
        existing = repository.get_latest_vocabulary_item_by_lemma(
            db,
            user_id=user_id,
            english_lemma=english_lemma,
        )
        created_new = existing is None or capture.force_new_vocabulary_item

        if created_new:
            vocabulary_item = repository.create_vocabulary_item(
                db,
                VocabularyItemCreate(
                    user_id=user_id,
                    english_lemma=english_lemma,
                    russian_translation=russian_translation,
                    context_definition_ru=definition_resolution.context_definition,
                    context_definition_source=definition_resolution.source,
                    context_definition_confidence=definition_resolution.confidence,
                    definition_reused_from_item_id=definition_resolution.reused_from_item_id,
                    source_sentence=capture.source_sentence,
                    source_url=capture.source_url,
                ),
                auto_commit=False,
            )
        else:
            vocabulary_item = existing

        context_memory_public_api.ensure_word_progress_entry(
            db=db,
            user_id=user_id,
            word=english_lemma,
        )
        learning_graph_public_api.register_vocabulary_semantics(
            db=db,
            user_id=user_id,
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            context_definition_ru=definition_resolution.context_definition,
            source_sentence=semantic_sentence,
            source_url=capture.source_url,
            vocabulary_item_id=vocabulary_item.id,
        )
    if created_new:
        db.refresh(vocabulary_item)

    return _to_capture_dto(vocabulary_item)
