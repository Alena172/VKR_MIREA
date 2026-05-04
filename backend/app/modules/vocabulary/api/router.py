from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.application import AsyncTaskResponse
from app.core.db import get_db
from app.modules.identity.api.dependencies import get_current_user_id
from app.modules.vocabulary.api.items_schemas import (
    VocabularyFromCaptureRequest,
    VocabularyFromCaptureRequestMe,
    VocabularyFromCaptureResponse,
    VocabularyItem,
    VocabularyItemCreate,
    VocabularyItemCreateMe,
    VocabularyItemUpdateMe,
)
from app.modules.vocabulary.api.translation_schemas import TranslateRequest, TranslateRequestMe, TranslateResponse
from app.modules.vocabulary.application.items_service import vocabulary_items_application_service
from app.modules.vocabulary.application.translation_service import translation_application_service
from app.modules.vocabulary.domain.items_contracts import VocabularyFromCaptureResultDTO, VocabularyItemDTO


router = APIRouter()


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
        vocabulary=_to_vocabulary_response(result.vocabulary),
    )


@router.get("/vocabulary/me", response_model=list[VocabularyItem])
def list_my_items(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[VocabularyItem]:
    return [
        _to_vocabulary_response(item)
        for item in vocabulary_items_application_service.list_items(
            db=db,
            requested_user_id=current_user_id,
            current_user_id=current_user_id,
        )
    ]


@router.get("/vocabulary", response_model=list[VocabularyItem])
def list_items(
    user_id: int | None = Query(default=None, ge=1),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[VocabularyItem]:
    return [
        _to_vocabulary_response(item)
        for item in vocabulary_items_application_service.list_items(
            db=db,
            requested_user_id=user_id,
            current_user_id=current_user_id,
        )
    ]


@router.post("/vocabulary/me", response_model=AsyncTaskResponse, status_code=202)
def add_my_item(
    payload: VocabularyItemCreateMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return vocabulary_items_application_service.queue_add_item(
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


@router.post("/vocabulary", response_model=AsyncTaskResponse, status_code=202)
def add_item(
    payload: VocabularyItemCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return vocabulary_items_application_service.queue_add_item(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )


@router.post("/vocabulary/me/from-capture", response_model=AsyncTaskResponse, status_code=202)
def add_my_item_from_capture(
    payload: VocabularyFromCaptureRequestMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return vocabulary_items_application_service.queue_add_item_from_capture(
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


@router.post("/vocabulary/from-capture", response_model=AsyncTaskResponse, status_code=202)
def add_item_from_capture(
    payload: VocabularyFromCaptureRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return vocabulary_items_application_service.queue_add_item_from_capture(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )


@router.put("/vocabulary/me/{item_id}", response_model=VocabularyItem)
def update_my_item(
    item_id: int,
    payload: VocabularyItemUpdateMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> VocabularyItem:
    result = vocabulary_items_application_service.update_item(
        db=db,
        item_id=item_id,
        payload=payload,
        current_user_id=current_user_id,
    )
    return _to_vocabulary_response(result)


@router.delete("/vocabulary/me/{item_id}")
def delete_my_item(
    item_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    return vocabulary_items_application_service.delete_item(
        db=db,
        item_id=item_id,
        current_user_id=current_user_id,
    )


@router.post("/translate/me", response_model=TranslateResponse)
async def translate_me(
    payload: TranslateRequestMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TranslateResponse:
    result = await translation_application_service.translate_for_user(
        db=db,
        user_id=current_user_id,
        text=payload.text,
        source_context=payload.source_context,
    )
    return TranslateResponse(
        translated_text=result.translated_text,
        note=result.note,
    )


@router.post("/translate", response_model=TranslateResponse)
async def translate(
    payload: TranslateRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TranslateResponse:
    user_id = translation_application_service.resolve_target_user_id(
        requested_user_id=payload.user_id,
        current_user_id=current_user_id,
    )
    result = await translation_application_service.translate_for_user(
        db=db,
        user_id=user_id,
        text=payload.text,
        source_context=payload.source_context,
    )
    return TranslateResponse(
        translated_text=result.translated_text,
        note=result.note,
    )
