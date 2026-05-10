from fastapi import APIRouter

from app.modules.ai.router import router as ai_router
from app.modules.graph.router import router as graph_router
from app.modules.identity.router import router as identity_router
from app.modules.review.router import router as review_router
from app.modules.training.router import router as training_router
from app.modules.vocabulary.router import router as vocabulary_router
from app.platform.tasks.router import router as tasks_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(identity_router)
api_router.include_router(vocabulary_router)
api_router.include_router(training_router)
api_router.include_router(review_router)
api_router.include_router(graph_router)
api_router.include_router(ai_router)
api_router.include_router(tasks_router)
