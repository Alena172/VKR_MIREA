from fastapi import APIRouter

from app.modules.learning_graph.router import router as learning_graph_router

router = APIRouter()
router.include_router(learning_graph_router)
