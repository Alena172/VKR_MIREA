"""Точка сборки FastAPI-приложения и общих middleware."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.api import api_router
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.schema import ensure_database_schema_ready

settings = get_settings()


class _HealthcheckAccessLogFilter(logging.Filter):
    """Скрывает шумные access-логи healthcheck-эндпоинта."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return '"GET /health HTTP/1.1" 200' not in message

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
def on_startup() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(current_filter, _HealthcheckAccessLogFilter) for current_filter in access_logger.filters):
        access_logger.addFilter(_HealthcheckAccessLogFilter())

    if not settings.bootstrap_schema_on_startup:
        return

    ensure_database_schema_ready(engine=engine, database_url=settings.database_url)


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    """Простой healthcheck для Docker, gateway и ручной проверки API."""

    return {"status": "ok"}
