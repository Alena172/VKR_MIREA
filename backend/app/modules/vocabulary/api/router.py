from fastapi import APIRouter

from app.modules.vocabulary.api.items_router import router as items_router
from app.modules.vocabulary.api.translation_router import router as translation_router

router = APIRouter()
router.include_router(items_router)
router.include_router(translation_router)
