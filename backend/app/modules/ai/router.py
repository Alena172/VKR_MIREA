from fastapi import APIRouter

from app.modules.ai.facade import ai_facade
from app.modules.ai.schemas import (
    AIStatusResponse,
    ExplainErrorRequest,
    ExplainErrorResponse,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/explain-error", response_model=ExplainErrorResponse)
async def explain_error(payload: ExplainErrorRequest) -> ExplainErrorResponse:
    return await ai_facade.explain_error_async(payload)


@router.get("/status", response_model=AIStatusResponse)
def status() -> AIStatusResponse:
    return ai_facade.get_status()
