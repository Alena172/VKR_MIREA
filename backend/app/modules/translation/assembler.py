from __future__ import annotations

from app.modules.translation.contracts import TranslationResultDTO


def to_translation_result_dto(*, translated_text: str, note: str) -> TranslationResultDTO:
    return TranslationResultDTO(
        translated_text=translated_text,
        note=note,
    )
