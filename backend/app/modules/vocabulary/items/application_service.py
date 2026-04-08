from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.celery_app import enqueue_task
from app.core.application import AsyncTaskResponse, application_access, application_transaction
from app.modules.learning_graph.public_api import learning_graph_public_api
from app.modules.vocabulary.items.assembler import to_vocabulary_item_dto
from app.modules.vocabulary.items.contracts import VocabularyItemDTO
from app.modules.vocabulary.items.repository import vocabulary_repository
from app.modules.vocabulary.items.schemas import (
    VocabularyFromCaptureRequest,
    VocabularyItemCreate,
    VocabularyItemUpdateMe,
)


class VocabularyItemsApplicationService:
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

    def queue_add_item(
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

    def queue_add_item_from_capture(
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


vocabulary_items_application_service = VocabularyItemsApplicationService()
