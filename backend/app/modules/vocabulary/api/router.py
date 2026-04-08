from fastapi import APIRouter

from app.modules.vocabulary.items.router import router as items_router
from app.modules.vocabulary.translation.router import router as translation_router

router = APIRouter()
router.include_router(items_router)
router.include_router(translation_router)
