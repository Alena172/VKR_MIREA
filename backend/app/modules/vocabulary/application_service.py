from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.celery_app import enqueue_task
from app.core.application import AsyncTaskResponse, application_access, application_transaction
from app.modules.ai_services.contracts import TranslateWithContextRequest
from app.modules.ai_services.service import ai_service
from app.modules.base_lexicon.public_api import base_lexicon_public_api
from app.modules.capture.public_api import capture_public_api
from app.modules.capture.schemas import CaptureCreate
from app.modules.context_memory.public_api import context_memory_public_api
from app.modules.learning_graph.public_api import learning_graph_public_api
from app.modules.vocabulary.assembler import (
    to_vocabulary_from_capture_result_dto,
    to_vocabulary_item_dto,
)
from app.modules.vocabulary.contracts import VocabularyFromCaptureResultDTO, VocabularyItemDTO

from app.modules.vocabulary.repository import vocabulary_repository
from app.modules.vocabulary.schemas import (
    VocabularyFromCaptureRequest,
    VocabularyItemCreate,
    VocabularyItemUpdateMe,
)

class VocabularyApplicationService:
    _ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
    _RUSSIAN_TOKEN_RE = re.compile(r"[А-Яа-яЁё-]+")

    def list_items(
        self,
        *,
        db: Session,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> list[VocabularyItemDTO]:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=requested_user_id,
            current_user_id=current_user_id,
        )
        return [to_vocabulary_item_dto(item) for item in vocabulary_repository.list_items(db, user_id=target_user_id)]

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

        task = enqueue_task(
            add_word_with_ai,
            owner_user_id=current_user_id,
            kwargs={
                "user_id": target_user_id,
                "english_lemma": payload.english_lemma.strip().lower(),
                "russian_translation": payload.russian_translation.strip(),
                "source_sentence": payload.source_sentence.strip() if payload.source_sentence else None,
                "source_url": payload.source_url.strip() if payload.source_url else None,
            },
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
    ) -> VocabularyItemDTO:
        application_access.ensure_user_exists(db=db, user_id=user_id)

        normalized_lemma = english_lemma.strip().lower()
        normalized_translation = russian_translation.strip()
        normalized_sentence = source_sentence.strip() if source_sentence else None
        normalized_url = source_url.strip() if source_url else None

        context_definition_ru = await ai_service.generate_context_definition_async(
            english_lemma=normalized_lemma,
            russian_translation=normalized_translation,
            source_sentence=normalized_sentence,
        )

        with application_transaction.boundary(db=db):
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
        return to_vocabulary_item_dto(item)

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

        task = enqueue_task(
            study_flow_capture_to_vocabulary,
            owner_user_id=current_user_id,
            kwargs={
                "user_id": target_user_id,
                "selected_text": payload.selected_text,
                "source_url": payload.source_url,
                "source_sentence": payload.source_sentence,
                "force_new_vocabulary_item": payload.force_new_vocabulary_item,
            },
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
    ) -> VocabularyFromCaptureResultDTO:
        user = application_access.get_user_or_404(db=db, user_id=user_id)
        normalized_sentence = source_sentence.strip() if source_sentence else None
        normalized_url = source_url.strip() if source_url else None

        (
            russian_translation,
            context_definition_ru,
            translation_note,
            semantic_sentence,
        ) = await self._generate_capture_ai_data(
            selected_text=selected_text,
            english_lemma=self._normalize_english_lemma(selected_text),
            cefr_level=user.cefr_level,
            source_sentence=normalized_sentence,
            db=db,
        )

        with application_transaction.boundary(db=db):
            capture = capture_public_api.create(
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

            queued_for_review = context_memory_public_api.ensure_word_progress_entry(
                db=db,
                user_id=user_id,
                word=english_lemma,
            ).tracked
            learning_graph_public_api.register_vocabulary_semantics(
                db=db,
                user_id=user_id,
                english_lemma=english_lemma,
                russian_translation=russian_translation,
                context_definition_ru=context_definition_ru,
                source_sentence=semantic_sentence,
                source_url=normalized_url,
                vocabulary_item_id=vocabulary_item.id,
            )
        if created_new:
            db.refresh(vocabulary_item)

        return to_vocabulary_from_capture_result_dto(
            capture=capture,
            vocabulary=to_vocabulary_item_dto(vocabulary_item),
            translation_note=translation_note,
            created_new_vocabulary_item=created_new,
            queued_for_review=queued_for_review,
        )

    def update_item(
        self,
        *,
        db: Session,
        item_id: int,
        payload: VocabularyItemUpdateMe,
        current_user_id: int,
    ) -> VocabularyItemDTO:
        item = vocabulary_repository.get_by_id_for_user(db, item_id=item_id, user_id=current_user_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Vocabulary item not found")

        updated = vocabulary_repository.update(
            db,
            item,
            english_lemma=payload.english_lemma,
            russian_translation=payload.russian_translation,
            source_sentence=payload.source_sentence,
            source_url=payload.source_url,
        )
        return to_vocabulary_item_dto(updated)

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
        with application_transaction.boundary(db=db):
            learning_graph_public_api.delete_vocabulary_links(
                db=db,
                user_id=current_user_id,
                vocabulary_item_id=item.id,
            )
            vocabulary_repository.delete(db, item, auto_commit=False)
        return {"deleted": True}

    def _normalize_english_lemma(self, text: str) -> str:
        return text.strip().split()[0].lower()

    def _normalize_translation(self, text: str) -> str:
        value = text.strip()
        if value.startswith("[RU]"):
            value = value.replace("[RU]", "", 1).strip()
        return value or "перевод не найден"

    def _english_tokens(self, text: str | None) -> list[str]:
        return [token.lower() for token in self._ENGLISH_TOKEN_RE.findall(text or "")]

    def _russian_tokens(self, text: str | None) -> list[str]:
        return [token.lower() for token in self._RUSSIAN_TOKEN_RE.findall(text or "")]

    def _is_single_word_capture(self, text: str) -> bool:
        return len(self._english_tokens(text)) == 1

    def _looks_like_context_phrase_expansion(
        self,
        *,
        base_translation: str,
        contextual_translation: str,
    ) -> bool:
        base_tokens = self._russian_tokens(base_translation)
        contextual_tokens = self._russian_tokens(contextual_translation)
        if not base_tokens or not contextual_tokens:
            return False
        if base_tokens == contextual_tokens:
            return False
        if len(base_tokens) == 1 and len(contextual_tokens) >= 2:
            return True
        return False

    async def _generate_capture_ai_data(
        self,
        *,
        selected_text: str,
        english_lemma: str,
        cefr_level: str,
        source_sentence: str | None,
        db: Session,
    ) -> tuple[str, str, str, str | None]:
        if self._is_single_word_capture(selected_text):
            fast_translation = base_lexicon_public_api.lookup_translation(
                db=db,
                english_lemma=english_lemma,
            ) or ai_service.fast_translate_single_word(english_lemma)
            if fast_translation:
                normalized_fast_translation = self._normalize_translation(fast_translation)
                return (
                    normalized_fast_translation,
                    ai_service.generate_context_definition_fast(
                        english_lemma=english_lemma,
                        russian_translation=normalized_fast_translation,
                        source_sentence=source_sentence,
                    ),
                    "fast_local_word_translation; local_definition",
                    None,
                )

        contextual_response = await ai_service.translate_with_context_async(
            TranslateWithContextRequest(
                text=english_lemma,
                cefr_level=cefr_level,
                source_context=source_sentence,
            )
        )
        contextual_translation = self._normalize_translation(contextual_response.translated_text)

        translation_note = contextual_response.provider_note
        semantic_sentence = source_sentence
        russian_translation = contextual_translation

        if self._is_single_word_capture(selected_text):
            base_response = await ai_service.translate_with_context_async(
                TranslateWithContextRequest(
                    text=english_lemma,
                    cefr_level=cefr_level,
                    source_context=None,
                )
            )
            base_translation = self._normalize_translation(base_response.translated_text)

            if self._looks_like_context_phrase_expansion(
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

        context_definition_ru = await ai_service.generate_context_definition_async(
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            source_sentence=semantic_sentence,
            cefr_level=cefr_level,
        )
        return russian_translation, context_definition_ru, translation_note, semantic_sentence


vocabulary_application_service = VocabularyApplicationService()
