from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.celery_app import enqueue_task
from app.core.application import (
    AsyncTaskResponse,
    application_access,
    application_transaction,
)
from app.modules.graph.service.graph import graph_service as learning_graph_public_api
from app.modules.vocabulary import repository
from app.modules.vocabulary.schemas import (
    VocabularyFromCaptureRequest,
    VocabularyItemCreate,
    VocabularyItemDTO,
    VocabularyItemUpdateMe,
)
from app.modules.vocabulary.service.definition import resolve_context_definition


def _to_dto(uv, entry) -> VocabularyItemDTO:
    return VocabularyItemDTO.from_model(uv, entry)


def list_items(
    *,
    db: Session,
    requested_user_id: int | None,
    current_user_id: int,
) -> list[VocabularyItemDTO]:
    target_user_id = application_access.resolve_target_user_id(
        requested_user_id=requested_user_id,
        current_user_id=current_user_id,
    )
    return [_to_dto(uv, entry) for uv, entry in repository.list_user_vocabulary(db, user_id=target_user_id)]


def list_user_items(*, db: Session, user_id: int) -> list[VocabularyItemDTO]:
    return [_to_dto(uv, entry) for uv, entry in repository.list_user_vocabulary(db, user_id=user_id)]


def get_translation_map_for_user(
    db: Session,
    *,
    user_id: int,
    english_lemmas: list[str],
) -> dict[str, str]:
    return repository.get_translation_map(db, user_id=user_id, english_lemmas=english_lemmas)


def get_definition_map_for_user(
    db: Session,
    *,
    user_id: int,
    english_lemmas: list[str],
) -> dict[str, str]:
    return repository.get_definition_map(db, user_id=user_id, english_lemmas=english_lemmas)


def list_english_lemmas_for_user(db: Session, *, user_id: int) -> list[str]:
    return repository.list_english_lemmas(db, user_id=user_id)


def get_latest_item_by_lemma(
    db: Session,
    *,
    user_id: int,
    english_lemma: str,
) -> VocabularyItemDTO | None:
    row = repository.get_latest_vocabulary_item_by_lemma(db, user_id=user_id, english_lemma=english_lemma)
    return _to_dto(row[0], row[1]) if row is not None else None


def queue_add_item(
    *,
    db: Session,
    payload: VocabularyItemCreate,
    current_user_id: int,
) -> AsyncTaskResponse:
    target_user_id = application_access.resolve_target_user_id(
        requested_user_id=payload.user_id,
        current_user_id=current_user_id,
    )
    application_access.get_user_or_404(db=db, user_id=target_user_id)

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
    *,
    db: Session,
    payload: VocabularyFromCaptureRequest,
    current_user_id: int,
) -> AsyncTaskResponse:
    target_user_id = application_access.resolve_target_user_id(
        requested_user_id=payload.user_id,
        current_user_id=current_user_id,
    )
    application_access.get_user_or_404(db=db, user_id=target_user_id)

    from app.tasks.vocabulary_tasks import capture_to_vocabulary_task

    task = enqueue_task(
        capture_to_vocabulary_task,
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


async def create_item_with_ai(
    *,
    db: Session,
    user_id: int,
    english_lemma: str,
    russian_translation: str,
    source_sentence: str | None,
    source_url: str | None,
) -> VocabularyItemDTO:
    application_access.get_user_or_404(db=db, user_id=user_id)

    normalized_lemma = english_lemma.strip().lower()
    normalized_translation = russian_translation.strip()
    normalized_sentence = source_sentence.strip() if source_sentence else None
    normalized_url = source_url.strip() if source_url else None

    definition_resolution = await resolve_context_definition(
        db=db,
        english_lemma=normalized_lemma,
        russian_translation=normalized_translation,
        source_sentence=normalized_sentence,
    )

    with application_transaction.boundary(db=db):
        entry, _ = repository.get_or_create_dictionary_entry(
            db,
            english_lemma=normalized_lemma,
            russian_translation=normalized_translation,
            context_definition_ru=definition_resolution.context_definition,
        )
        uv, _ = repository.add_to_user_vocabulary(
            db,
            user_id=user_id,
            entry_id=entry.id,
            source_sentence=normalized_sentence,
            source_url=normalized_url,
        )

    db.refresh(uv)
    db.refresh(entry)
    return _to_dto(uv, entry)


def update_item(
    *,
    db: Session,
    item_id: int,
    payload: VocabularyItemUpdateMe,
    current_user_id: int,
) -> VocabularyItemDTO:
    row = repository.get_user_vocabulary_item(db, user_id=current_user_id, item_id=item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
    uv, entry = row
    repository.update_user_vocabulary_item(
        db, uv,
        source_sentence=payload.source_sentence,
        source_url=payload.source_url,
    )
    return _to_dto(uv, entry)


def delete_item(
    *,
    db: Session,
    item_id: int,
    current_user_id: int,
) -> dict[str, bool]:
    row = repository.get_user_vocabulary_item(db, user_id=current_user_id, item_id=item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
    uv, _ = row
    with application_transaction.boundary(db=db):
        learning_graph_public_api.delete_vocabulary_links(
            db=db,
            user_id=current_user_id,
            vocabulary_item_id=uv.id,
        )
        repository.delete_user_vocabulary_item(db, uv)
    return {"deleted": True}
