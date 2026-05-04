from fastapi import APIRouter

from app.modules.ai_services.api.router import router as ai_services_router
from app.modules.identity.api.router import router as identity_router
from app.modules.learning.api.router import router as learning_router
from app.modules.learning_graph.api.router import router as learning_graph_router
from app.platform.tasks.router import router as tasks_router
from app.modules.vocabulary.api.router import router as vocabulary_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(identity_router)
api_router.include_router(vocabulary_router)
api_router.include_router(learning_router)
api_router.include_router(learning_graph_router)
api_router.include_router(ai_services_router)
api_router.include_router(tasks_router)
