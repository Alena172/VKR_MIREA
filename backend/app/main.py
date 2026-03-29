from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.api import api_router
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.modules.base_lexicon.public_api import base_lexicon_public_api

settings = get_settings()

app = FastAPI(
    title="VKR English Learning API",
    version="0.1.0",
    summary="Modular monolith for RU-native users learning English",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts_list,
)

app.include_router(api_router)


@app.on_event("startup")
def ensure_base_lexicon_seeded() -> None:
    db = SessionLocal()
    try:
        base_lexicon_public_api.ensure_seeded(db)
    finally:
        db.close()


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
