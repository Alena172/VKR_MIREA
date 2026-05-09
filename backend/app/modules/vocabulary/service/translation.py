from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.application import application_access
from app.modules.ai_services.contracts import TranslateWithContextRequest
from app.modules.ai_services.public_api import TranslationProviderUnavailableError, ai_service
from app.modules.identity.service import get_user_or_404
from app.modules.vocabulary.service.items import list_user_items
from app.modules.vocabulary.schemas import TranslationResultDTO


def _build_translation_note(provider_note: str) -> str:
    normalized = provider_note.strip().lower()
    if normalized.startswith("local_heuristic"):
        return f"Local heuristic translation used ({provider_note})"
    if normalized.startswith("ai_disambiguation:"):
        return f"AI disambiguation used ({provider_note})"
    if normalized.startswith("ai_translation:"):
        return f"AI translation used ({provider_note})"
    if normalized.startswith("glossary"):
        return f"Glossary translation used ({provider_note})"
    return f"Translation completed ({provider_note})"


async def translate_for_user(
    *,
    db: Session,
    user_id: int,
    text: str,
    source_context: str | None,
) -> TranslationResultDTO:
    user = get_user_or_404(db=db, user_id=user_id)

    try:
        ai_response = await ai_service.translate_with_context_async(
            TranslateWithContextRequest(
                text=text,
                cefr_level=user.cefr_level,
                source_context=source_context,
                glossary=[
                    {
                        "english_term": item.english_lemma,
                        "russian_translation": item.russian_translation,
                        "source_sentence": item.source_sentence,
                    }
                    for item in list_user_items(db=db, user_id=user_id)[:50]
                ],
            )
        )
    except TranslationProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return TranslationResultDTO(
        translated_text=ai_response.translated_text,
        note=_build_translation_note(ai_response.provider_note),
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
