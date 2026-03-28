from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.exercise_engine.application_service import (
    AsyncTaskResponse,
    exercise_engine_application_service,
)
from app.modules.exercise_engine.schemas import (
    ExerciseGenerateRequest,
    ExerciseGenerateRequestMe,
)

router = APIRouter(prefix="/exercises", tags=["exercise_engine"])


@router.post("/me/generate", response_model=AsyncTaskResponse, status_code=202)
def generate_me(
    payload: ExerciseGenerateRequestMe,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return exercise_engine_application_service.queue_generation(
        db=db,
        payload=ExerciseGenerateRequest(
            user_id=current_user_id,
            vocabulary_ids=payload.vocabulary_ids,
            size=payload.size,
            mode=payload.mode,
        ),
        current_user_id=current_user_id,
    )


@router.post("/generate", response_model=AsyncTaskResponse, status_code=202)
def generate(
    payload: ExerciseGenerateRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AsyncTaskResponse:
    return exercise_engine_application_service.queue_generation(
        db=db,
        payload=payload,
        current_user_id=current_user_id,
    )
