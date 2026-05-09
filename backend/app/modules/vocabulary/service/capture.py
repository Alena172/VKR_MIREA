from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.application import application_access, application_transaction
from app.core.config import get_settings
from app.core.libretranslate_client import LibreTranslateClient
from app.modules.review.service.srs import srs_service as context_memory_public_api
from app.modules.graph.service.graph import graph_service as learning_graph_public_api
from app.modules.vocabulary import repository
from app.modules.vocabulary.models import CaptureModel
from app.modules.vocabulary.schemas import CaptureDTO, VocabularyItemCreate, VocabularyItemDTO
from app.modules.vocabulary.service.definition import resolve_context_definition
from app.modules.vocabulary.service.lexicon import lookup_translation

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


def _russian_tokens(text: str | None) -> list[str]:
    return [token.lower() for token in _RUSSIAN_TOKEN_RE.findall(text or "")]


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


def _make_libretranslate_client() -> LibreTranslateClient:
    settings = get_settings()
    return LibreTranslateClient(
        base_url=settings.libretranslate_url,
        api_key=settings.libretranslate_api_key,
        timeout_seconds=settings.libretranslate_timeout_seconds,
    )


async def _resolve_translation(
    *,
    db: Session,
    english_lemma: str,
    source_sentence: str | None,
) -> tuple[str, str | None]:
    """Возвращает (russian_translation, semantic_sentence).

    Приоритет: base_lexicon (без контекста) → LibreTranslate с контекстом →
    LibreTranslate без контекста → fallback "перевод не найден".

    Для single-word capture с контекстом: если LibreTranslate вернул
    многословный результат вместо перевода одного слова, берём перевод
    без контекста и не сохраняем предложение как семантический ключ.
    """
    lexicon = lookup_translation(db=db, english_lemma=english_lemma)
    if lexicon and not source_sentence:
        return _normalize_translation(lexicon), None

    client = _make_libretranslate_client()

    if source_sentence and client.is_configured():
        contextual = await client.translate(text=english_lemma, context=source_sentence)
        if contextual:
            contextual = _normalize_translation(contextual)
            base = None
            if client.is_configured():
                base_raw = await client.translate(text=english_lemma)
                base = _normalize_translation(base_raw) if base_raw else None
            if base and _looks_like_context_phrase_expansion(
                base_translation=base,
                contextual_translation=contextual,
            ):
                return base, None
            return contextual, source_sentence

    if client.is_configured():
        base_raw = await client.translate(text=english_lemma)
        if base_raw:
            return _normalize_translation(base_raw), None

    if lexicon:
        return _normalize_translation(lexicon), None

    return "перевод не найден", None


async def capture_to_vocabulary(
    *,
    db: Session,
    user_id: int,
    selected_text: str,
    source_url: str | None,
    source_sentence: str | None,
    force_new_vocabulary_item: bool,
) -> CaptureDTO:
    application_access.get_user_or_404(db=db, user_id=user_id)
    capture = CaptureModel(
        user_id=user_id,
        selected_text=selected_text,
        source_url=source_url.strip() if source_url else None,
        source_sentence=source_sentence.strip() if source_sentence else None,
        force_new_vocabulary_item=force_new_vocabulary_item,
    )
    english_lemma = _normalize_english_lemma(capture.selected_text)

    russian_translation, semantic_sentence = await _resolve_translation(
        db=db,
        english_lemma=english_lemma,
        source_sentence=capture.source_sentence,
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
