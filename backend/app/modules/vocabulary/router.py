from fastapi import APIRouter, Depends

from app.modules.identity.deps import get_current_user_id
from app.modules.vocabulary.schemas import (
    TranslateRequestMe,
    TranslateResponse,
    VocabularyFromCaptureRequestMe,
    VocabularyItemRead,
    VocabularyItemCreateMe,
    VocabularyItemUpdateMe,
)
from app.modules.vocabulary.service.items import VocabularyService

router = APIRouter()


@router.get("/vocabulary/me", response_model=list[VocabularyItemRead])
def list_my_items(
    current_user_id: int = Depends(get_current_user_id),
    service: VocabularyService = Depends(),
) -> list[VocabularyItemRead]:
    return [
        VocabularyItemRead.model_validate(item, from_attributes=True)
        for item in service.list_items(
            requested_user_id=current_user_id,
            current_user_id=current_user_id,
        )
    ]


@router.post("/vocabulary/me", response_model=VocabularyItemRead)
async def add_my_item(
    payload: VocabularyItemCreateMe,
    current_user_id: int = Depends(get_current_user_id),
    service: VocabularyService = Depends(),
) -> VocabularyItemRead:
    item = await service.create_item_with_ai(
        user_id=current_user_id,
        english_lemma=payload.english_lemma,
        russian_translation=payload.russian_translation,
        source_sentence=payload.source_sentence,
        source_url=payload.source_url,
    )
    return VocabularyItemRead.model_validate(item, from_attributes=True)


@router.post("/vocabulary/me/from-capture")
async def add_my_item_from_capture(
    payload: VocabularyFromCaptureRequestMe,
    current_user_id: int = Depends(get_current_user_id),
    service: VocabularyService = Depends(),
):
    item, created_new = await service.capture_to_vocabulary(
        user_id=current_user_id,
        selected_text=payload.selected_text,
        source_url=payload.source_url,
        source_sentence=payload.source_sentence,
        force_new_vocabulary_item=payload.force_new_vocabulary_item,
    )
    vocab_read = VocabularyItemRead.model_validate(item, from_attributes=True)
    return {
        "capture": {
            "selected_text": payload.selected_text,
            "source_url": payload.source_url,
            "source_sentence": payload.source_sentence,
        },
        "vocabulary": vocab_read.model_dump(),
        "created_new_vocabulary_item": created_new,
        "queued_for_review": True,
    }


@router.put("/vocabulary/me/{item_id}", response_model=VocabularyItemRead)
def update_my_item(
    item_id: int,
    payload: VocabularyItemUpdateMe,
    current_user_id: int = Depends(get_current_user_id),
    service: VocabularyService = Depends(),
) -> VocabularyItemRead:
    return VocabularyItemRead.model_validate(
        service.update_item(
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
    service: VocabularyService = Depends(),
) -> dict[str, bool]:
    return service.delete_item(
        item_id=item_id,
        current_user_id=current_user_id,
    )


@router.post("/translate/me", response_model=TranslateResponse)
async def translate_me(
    payload: TranslateRequestMe,
    current_user_id: int = Depends(get_current_user_id),
    service: VocabularyService = Depends(),
) -> TranslateResponse:
    result = await service.translate_for_user(
        user_id=current_user_id,
        text=payload.text,
        source_context=payload.source_context,
    )
    return TranslateResponse(
        translated_text=result.translated_text,
        note=result.note,
    )
