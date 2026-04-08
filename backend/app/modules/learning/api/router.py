from fastapi import APIRouter

from app.modules.learning.exercise_engine.router import router as exercise_engine_router
from app.modules.learning.review.router import router as review_router
from app.modules.learning.session.router import router as session_router

router = APIRouter()
router.include_router(exercise_engine_router)
router.include_router(session_router)
router.include_router(review_router)
