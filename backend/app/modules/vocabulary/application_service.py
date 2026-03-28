from __future__ import annotations

from app.core.application import AsyncTaskResponse, application_access, application_transaction
from app.modules.ai_services.contracts import TranslateWithContextRequest
from app.modules.ai_services.service import ai_service
from app.modules.capture.repository import capture_repository
from app.modules.capture.schemas import CaptureCreate, CaptureItem
from app.modules.context_memory.repository import context_repository
from app.modules.learning_graph.repository import learning_graph_repository
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.vocabulary.repository import vocabulary_repository
from app.modules.vocabulary.schemas import (
    VocabularyFromCaptureRequest,
    VocabularyFromCaptureResponse,
    VocabularyItem,
    VocabularyItemCreate,
    VocabularyItemUpdateMe,
)

class VocabularyApplicationService:
    def list_items(
        self,
        *,
        db: Session,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> list[VocabularyItem]:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=requested_user_id,
            current_user_id=current_user_id,
        )
        return vocabulary_repository.list_items(db, user_id=target_user_id)

    def add_item(
        self,
        *,
        db: Session,
        payload: VocabularyItemCreate,
        current_user_id: int,
    ) -> AsyncTaskResponse:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=payload.user_id,
            current_user_id=current_user_id,
        )
        application_access.ensure_user_exists(db=db, user_id=target_user_id)

        from app.tasks.vocabulary_tasks import add_word_with_ai

        task = add_word_with_ai.delay(
            user_id=target_user_id,
            english_lemma=payload.english_lemma.strip().lower(),
            russian_translation=payload.russian_translation.strip(),
            source_sentence=payload.source_sentence.strip() if payload.source_sentence else None,
            source_url=payload.source_url.strip() if payload.source_url else None,
        )
        return AsyncTaskResponse(task_id=task.id)

    async def create_item_with_ai(
        self,
        *,
        db: Session,
        user_id: int,
        english_lemma: str,
        russian_translation: str,
        source_sentence: str | None,
        source_url: str | None,
    ) -> VocabularyItem:
        application_access.ensure_user_exists(db=db, user_id=user_id)

        normalized_lemma = english_lemma.strip().lower()
        normalized_translation = russian_translation.strip()
        normalized_sentence = source_sentence.strip() if source_sentence else None
        normalized_url = source_url.strip() if source_url else None

        with application_transaction.boundary(db=db):
            context_definition_ru = await ai_service.generate_context_definition_async(
                english_lemma=normalized_lemma,
                russian_translation=normalized_translation,
                source_sentence=normalized_sentence,
            )
            item = vocabulary_repository.create(
                db,
                VocabularyItemCreate(
                    user_id=user_id,
                    english_lemma=normalized_lemma,
                    russian_translation=normalized_translation,
                    context_definition_ru=context_definition_ru,
                    source_sentence=normalized_sentence,
                    source_url=normalized_url,
                ),
                auto_commit=False,
            )
        db.refresh(item)
        return VocabularyItem.model_validate(item)

    def add_item_from_capture(
        self,
        *,
        db: Session,
        payload: VocabularyFromCaptureRequest,
        current_user_id: int,
    ) -> AsyncTaskResponse:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=payload.user_id,
            current_user_id=current_user_id,
        )
        application_access.ensure_user_exists(db=db, user_id=target_user_id)

        from app.tasks.vocabulary_tasks import study_flow_capture_to_vocabulary

        task = study_flow_capture_to_vocabulary.delay(
            user_id=target_user_id,
            selected_text=payload.selected_text,
            source_url=payload.source_url,
            source_sentence=payload.source_sentence,
            force_new_vocabulary_item=payload.force_new_vocabulary_item,
        )
        return AsyncTaskResponse(task_id=task.id)

    async def capture_to_vocabulary(
        self,
        *,
        db: Session,
        user_id: int,
        selected_text: str,
        source_url: str | None,
        source_sentence: str | None,
        force_new_vocabulary_item: bool,
    ) -> VocabularyFromCaptureResponse:
        user = application_access.get_user_or_404(db=db, user_id=user_id)
        normalized_sentence = source_sentence.strip() if source_sentence else None
        normalized_url = source_url.strip() if source_url else None

        with application_transaction.boundary(db=db):
            capture = capture_repository.create(
                db,
                CaptureCreate(
                    user_id=user_id,
                    selected_text=selected_text,
                    source_url=normalized_url,
                    source_sentence=normalized_sentence,
                ),
                auto_commit=False,
            )
            english_lemma = self._normalize_english_lemma(selected_text)
            russian_translation, context_definition_ru = await self._generate_capture_ai_data(
                english_lemma=english_lemma,
                cefr_level=user.cefr_level,
                source_sentence=normalized_sentence,
            )

            existing = vocabulary_repository.get_latest_by_lemma(
                db,
                user_id=user_id,
                english_lemma=english_lemma,
            )
            created_new = existing is None or force_new_vocabulary_item

            if created_new:
                vocabulary_item = vocabulary_repository.create(
                    db,
                    VocabularyItemCreate(
                        user_id=user_id,
                        english_lemma=english_lemma,
                        russian_translation=russian_translation,
                        context_definition_ru=context_definition_ru,
                        source_sentence=normalized_sentence,
                        source_url=normalized_url,
                    ),
                    auto_commit=False,
                )
            else:
                vocabulary_item = existing

            progress = context_repository.ensure_word_progress(db, user_id=user_id, word=english_lemma)
            learning_graph_repository.semantic_upsert(
                db,
                user_id=user_id,
                english_lemma=english_lemma,
                russian_translation=russian_translation,
                context_definition_ru=context_definition_ru,
                source_sentence=normalized_sentence,
                source_url=normalized_url,
                vocabulary_item_id=vocabulary_item.id,
            )
        db.refresh(capture)
        if created_new:
            db.refresh(vocabulary_item)

        return VocabularyFromCaptureResponse(
            capture=CaptureItem.model_validate(capture),
            vocabulary=VocabularyItem.model_validate(vocabulary_item),
            translation_note="AI translation used (worker)",
            created_new_vocabulary_item=created_new,
            queued_for_review=progress is not None,
        )

    def update_item(
        self,
        *,
        db: Session,
        item_id: int,
        payload: VocabularyItemUpdateMe,
        current_user_id: int,
    ) -> VocabularyItem:
        item = vocabulary_repository.get_by_id_for_user(db, item_id=item_id, user_id=current_user_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Vocabulary item not found")

        return vocabulary_repository.update(
            db,
            item,
            english_lemma=payload.english_lemma,
            russian_translation=payload.russian_translation,
            source_sentence=payload.source_sentence,
            source_url=payload.source_url,
        )

    def delete_item(
        self,
        *,
        db: Session,
        item_id: int,
        current_user_id: int,
    ) -> dict[str, bool]:
        item = vocabulary_repository.get_by_id_for_user(db, item_id=item_id, user_id=current_user_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Vocabulary item not found")
        vocabulary_repository.delete(db, item)
        return {"deleted": True}

    def _normalize_english_lemma(self, text: str) -> str:
        return text.strip().split()[0].lower()

    def _normalize_translation(self, text: str) -> str:
        value = text.strip()
        if value.startswith("[RU]"):
            value = value.replace("[RU]", "", 1).strip()
        return value or "перевод не найден"

    async def _generate_capture_ai_data(
        self,
        *,
        english_lemma: str,
        cefr_level: str,
        source_sentence: str | None,
    ) -> tuple[str, str]:
        ai_response = await ai_service.translate_with_context_async(
            TranslateWithContextRequest(
                text=english_lemma,
                cefr_level=cefr_level,
                source_context=source_sentence,
            )
        )
        russian_translation = self._normalize_translation(ai_response.translated_text)
        context_definition_ru = await ai_service.generate_context_definition_async(
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            source_sentence=source_sentence,
            cefr_level=cefr_level,
        )
        return russian_translation, context_definition_ru


vocabulary_application_service = VocabularyApplicationService()
