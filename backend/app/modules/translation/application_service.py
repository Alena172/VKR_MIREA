from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.application import application_access
from app.modules.ai_services.contracts import TranslateWithContextRequest
from app.modules.ai_services.service import TranslationProviderUnavailableError, ai_service
from app.modules.context_memory.public_api import context_memory_public_api
from app.modules.translation.assembler import to_translation_result_dto
from app.modules.translation.contracts import TranslationResultDTO
from app.modules.users.public_api import users_public_api
from app.modules.vocabulary.public_api import vocabulary_public_api


class TranslationApplicationService:
    async def translate_for_user(
        self,
        *,
        db: Session,
        user_id: int,
        text: str,
        source_context: str | None,
    ) -> TranslationResultDTO:
        user = users_public_api.get_or_404(db=db, user_id=user_id)

        cefr_level = context_memory_public_api.get_effective_cefr_dto(
            db=db,
            user_id=user_id,
            fallback_cefr=user.cefr_level,
        ).cefr_level
        vocabulary_items = vocabulary_public_api.list_items(db, user_id=user_id)[:50]

        try:
            ai_response = await ai_service.translate_with_context_async(
                TranslateWithContextRequest(
                    text=text,
                    cefr_level=cefr_level,
                    source_context=source_context,
                    glossary=[
                        {
                            "english_term": item.english_lemma,
                            "russian_translation": item.russian_translation,
                            "source_sentence": item.source_sentence,
                        }
                        for item in vocabulary_items
                    ],
                )
            )
        except TranslationProviderUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return to_translation_result_dto(
            translated_text=ai_response.translated_text,
            note=f"AI translation used ({ai_response.provider_note})",
        )

    def resolve_target_user_id(
        self,
        *,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> int:
        return application_access.resolve_target_user_id(
            requested_user_id=requested_user_id,
            current_user_id=current_user_id,
        )


translation_application_service = TranslationApplicationService()
