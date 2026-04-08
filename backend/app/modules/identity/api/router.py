from fastapi import APIRouter

from app.modules.identity.auth.router import router as auth_router
from app.modules.identity.users.router import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
