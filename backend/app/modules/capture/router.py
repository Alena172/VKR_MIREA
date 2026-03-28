from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.capture.application_service import capture_application_service
from app.modules.capture.schemas import CaptureCreate, CaptureCreateMe, CaptureItem

router = APIRouter(prefix="/capture", tags=["capture"])


@router.get("/me", response_model=list[CaptureItem])
def list_my_capture(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[CaptureItem]:
    return capture_application_service.list_items(
        db=db,
        requested_user_id=current_user_id,
        current_user_id=current_user_id,
    )


@router.get("", response_model=list[CaptureItem])
def list_capture(
    user_id: int | None = Query(default=None, ge=1),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[CaptureItem]:
    return capture_application_service.list_items(
        db=db,
        requested_user_id=user_id,
        current_user_id=current_user_id,
    )


@router.post("/me", response_model=CaptureItem)
def create_my_capture(
    payload: CaptureCreateMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CaptureItem:
    return capture_application_service.create_item(
        db=db,
        payload=CaptureCreate(
            user_id=current_user_id,
            selected_text=payload.selected_text,
            source_url=payload.source_url,
            source_sentence=payload.source_sentence,
        ),
        current_user_id=current_user_id,
    )


@router.post("", response_model=CaptureItem)
def create_capture(
    payload: CaptureCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CaptureItem:
    return capture_application_service.create_item(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )
