from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.application import AsyncTaskResponse
from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.capture.schemas import CaptureItem
from app.modules.vocabulary.application_service import vocabulary_application_service
from app.modules.vocabulary.contracts import VocabularyFromCaptureResultDTO, VocabularyItemDTO
from app.modules.vocabulary.schemas import (
    VocabularyFromCaptureRequest,
    VocabularyFromCaptureRequestMe,
    VocabularyFromCaptureResponse,
    VocabularyItem,
    VocabularyItemCreate,
    VocabularyItemCreateMe,
    VocabularyItemUpdateMe,
)

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


def _to_vocabulary_response(item: VocabularyItemDTO) -> VocabularyItem:
    return VocabularyItem(
        id=item.id,
        user_id=item.user_id,
        english_lemma=item.english_lemma,
        russian_translation=item.russian_translation,
        context_definition_ru=item.context_definition_ru,
        context_definition_source=item.context_definition_source,
        context_definition_confidence=item.context_definition_confidence,
        definition_reused_from_item_id=item.definition_reused_from_item_id,
        source_sentence=item.source_sentence,
        source_url=item.source_url,
    )


def _to_vocabulary_from_capture_response(result: VocabularyFromCaptureResultDTO) -> VocabularyFromCaptureResponse:
    return VocabularyFromCaptureResponse(
        capture=CaptureItem(
            id=result.capture.id,
            user_id=result.capture.user_id,
            selected_text=result.capture.selected_text,
            source_url=result.capture.source_url,
            source_sentence=result.capture.source_sentence,
        ),
        vocabulary=_to_vocabulary_response(result.vocabulary),
        translation_note=result.translation_note,
        created_new_vocabulary_item=result.created_new_vocabulary_item,
        queued_for_review=result.queued_for_review,
    )


@router.get("/me", response_model=list[VocabularyItem])
def list_my_items(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[VocabularyItem]:
    return [
        _to_vocabulary_response(item)
        for item in vocabulary_application_service.list_items(
            db=db,
            requested_user_id=current_user_id,
            current_user_id=current_user_id,
        )
    ]


@router.get("", response_model=list[VocabularyItem])
def list_items(
    user_id: int | None = Query(default=None, ge=1),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[VocabularyItem]:
    return [
        _to_vocabulary_response(item)
        for item in vocabulary_application_service.list_items(
            db=db,
            requested_user_id=user_id,
            current_user_id=current_user_id,
        )
    ]


@router.post("/me", response_model=AsyncTaskResponse, status_code=202)
def add_my_item(
    payload: VocabularyItemCreateMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return vocabulary_application_service.add_item(
        db=db,
        payload=VocabularyItemCreate(
            user_id=current_user_id,
            english_lemma=payload.english_lemma,
            russian_translation=payload.russian_translation,
            source_sentence=payload.source_sentence,
            source_url=payload.source_url,
        ),
        current_user_id=current_user_id,
    )


@router.post("", response_model=AsyncTaskResponse, status_code=202)
def add_item(
    payload: VocabularyItemCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return vocabulary_application_service.add_item(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )


@router.post("/me/from-capture", response_model=AsyncTaskResponse, status_code=202)
def add_my_item_from_capture(
    payload: VocabularyFromCaptureRequestMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return vocabulary_application_service.add_item_from_capture(
        db=db,
        payload=VocabularyFromCaptureRequest(
            user_id=current_user_id,
            selected_text=payload.selected_text,
            source_url=payload.source_url,
            source_sentence=payload.source_sentence,
            force_new_vocabulary_item=payload.force_new_vocabulary_item,
        ),
        current_user_id=current_user_id,
    )


@router.post("/from-capture", response_model=AsyncTaskResponse, status_code=202)
def add_item_from_capture(
    payload: VocabularyFromCaptureRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return vocabulary_application_service.add_item_from_capture(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )


@router.put("/me/{item_id}", response_model=VocabularyItem)
def update_my_item(
    item_id: int,
    payload: VocabularyItemUpdateMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> VocabularyItem:
    result = vocabulary_application_service.update_item(
        db=db,
        item_id=item_id,
        payload=payload,
        current_user_id=current_user_id,
    )
    return _to_vocabulary_response(result)


@router.delete("/me/{item_id}")
def delete_my_item(
    item_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    return vocabulary_application_service.delete_item(
        db=db,
        item_id=item_id,
        current_user_id=current_user_id,
    )
