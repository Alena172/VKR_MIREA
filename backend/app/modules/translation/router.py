from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.translation.application_service import translation_application_service
from app.modules.translation.schemas import TranslateRequest, TranslateRequestMe, TranslateResponse

router = APIRouter(prefix="/translate", tags=["translation"])


@router.post("/me", response_model=TranslateResponse)
async def translate_me(
    payload: TranslateRequestMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TranslateResponse:
    return await translation_application_service.translate_for_user(
        db=db,
        user_id=current_user_id,
        text=payload.text,
        source_context=payload.source_context,
    )


@router.post("", response_model=TranslateResponse)
async def translate(
    payload: TranslateRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TranslateResponse:
    user_id = translation_application_service.resolve_target_user_id(
        requested_user_id=payload.user_id,
        current_user_id=current_user_id,
    )
    return await translation_application_service.translate_for_user(
        db=db,
        user_id=user_id,
        text=payload.text,
        source_context=payload.source_context,
    )
