from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.application import AsyncTaskResponse
from app.core.db import get_db
from app.modules.identity.deps import get_current_user_id
from app.modules.vocabulary.schemas import (
    TranslateRequest,
    TranslateRequestMe,
    TranslateResponse,
    VocabularyFromCaptureRequest,
    VocabularyFromCaptureRequestMe,
    VocabularyItemCreate,
    VocabularyItemCreateMe,
    VocabularyItemRead,
    VocabularyItemUpdateMe,
)
from app.modules.vocabulary.service.items import (
    delete_item,
    list_items,
    queue_add_item,
    queue_add_item_from_capture,
    update_item,
)
from app.modules.vocabulary.service.translation import (
    resolve_target_user_id,
    translate_for_user,
)

router = APIRouter()


@router.get("/vocabulary/me", response_model=list[VocabularyItemRead])
def list_my_items(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[VocabularyItemRead]:
    return [
        VocabularyItemRead.model_validate(item, from_attributes=True)
        for item in list_items(
            db=db,
            requested_user_id=current_user_id,
            current_user_id=current_user_id,
        )
    ]


@router.get("/vocabulary", response_model=list[VocabularyItemRead])
def list_vocabulary_items(
    user_id: int | None = Query(default=None, ge=1),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[VocabularyItemRead]:
    return [
        VocabularyItemRead.model_validate(item, from_attributes=True)
        for item in list_items(
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
    return queue_add_item(
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
    return queue_add_item(
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
    return queue_add_item_from_capture(
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
    return queue_add_item_from_capture(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )


@router.put("/vocabulary/me/{item_id}", response_model=VocabularyItemRead)
def update_my_item(
    item_id: int,
    payload: VocabularyItemUpdateMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> VocabularyItemRead:
    return VocabularyItemRead.model_validate(
        update_item(
            db=db,
            item_id=item_id,
            payload=payload,
            current_user_id=current_user_id,
        ),
        from_attributes=True,
    )


@router.delete("/vocabulary/me/{item_id}")
def delete_my_item(
    item_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    return delete_item(
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
    result = await translate_for_user(
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
    user_id = resolve_target_user_id(
        requested_user_id=payload.user_id,
        current_user_id=current_user_id,
    )
    result = await translate_for_user(
        db=db,
        user_id=user_id,
        text=payload.text,
        source_context=payload.source_context,
    )
    return TranslateResponse(
        translated_text=result.translated_text,
        note=result.note,
    )
