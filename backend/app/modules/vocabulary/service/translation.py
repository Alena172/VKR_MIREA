from __future__ import annotations

from app.core.application import application_access
from app.modules.vocabulary.schemas import TranslationResultDTO


async def translate_for_user(
    *,
    user_id: int,
    text: str,
    source_context: str | None,
    _service=None,
) -> TranslationResultDTO:
    """Тонкая совместимая обертка для старых тестов."""
    if _service is None:
        raise RuntimeError(
            "translate_for_user requires a VocabularyService instance. "
            "Use VocabularyService.translate_for_user() directly."
        )
    return await _service.translate_for_user(
        user_id=user_id,
        text=text,
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
