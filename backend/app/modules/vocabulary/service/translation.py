from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.application import application_access
from app.core.config import get_settings
from app.core.libretranslate_client import LibreTranslateClient
from app.modules.identity.service import get_user_or_404
from app.modules.vocabulary.schemas import TranslationResultDTO
from app.modules.vocabulary.service.lexicon import lookup_translation


def _get_libretranslate_client() -> LibreTranslateClient:
    settings = get_settings()
    return LibreTranslateClient(
        base_url=settings.libretranslate_url,
        api_key=settings.libretranslate_api_key,
        timeout_seconds=settings.libretranslate_timeout_seconds,
    )


async def translate_word_with_context(
    *,
    db: Session,
    english_lemma: str,
    source_context: str | None,
) -> TranslationResultDTO:
    lexicon_translation = lookup_translation(db=db, english_lemma=english_lemma)
    if lexicon_translation and not source_context:
        return TranslationResultDTO(
            translated_text=lexicon_translation,
            note="base_lexicon",
        )

    client = _get_libretranslate_client()
    if client.is_configured():
        result = await client.translate(
            text=english_lemma,
            context=source_context,
        )
        if result:
            return TranslationResultDTO(
                translated_text=result,
                note="libretranslate",
            )

    if lexicon_translation:
        return TranslationResultDTO(
            translated_text=lexicon_translation,
            note="base_lexicon_fallback",
        )

    raise HTTPException(status_code=503, detail="Translation service unavailable")


async def translate_for_user(
    *,
    db: Session,
    user_id: int,
    text: str,
    source_context: str | None,
) -> TranslationResultDTO:
    get_user_or_404(db=db, user_id=user_id)
    english_lemma = text.strip().lower().split()[0]
    return await translate_word_with_context(
        db=db,
        english_lemma=english_lemma,
        source_context=source_context,
    )


def resolve_target_user_id(
    *,
    requested_user_id: int | None,
    current_user_id: int,
) -> int:
    return application_access.resolve_target_user_id(
        requested_user_id=requested_user_id,
        current_user_id=current_user_id,
    )
