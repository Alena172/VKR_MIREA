from fastapi import APIRouter

from app.modules.ai_services.router import router as ai_services_router

router = APIRouter()
router.include_router(ai_services_router)
