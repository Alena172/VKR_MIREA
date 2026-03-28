"""Celery tasks for exercise generation.

Offloads AI exercise generation from the HTTP request cycle.
"""
from __future__ import annotations

import asyncio
import logging
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="exercises.generate_for_user",
    max_retries=1,
    default_retry_delay=3,
)
def generate_exercises_for_user(
    self,
    *,
    user_id: int,
    vocabulary_ids: list[int],
    size: int,
    mode: str,
) -> dict:
    """Generate exercises for a user and return them as a serialisable dict.

    The result matches ExerciseGenerateResponse schema.
    """
    from app.core.db import SessionLocal
    from app.modules.exercise_engine.application_service import exercise_engine_application_service

    db = SessionLocal()
    try:
        response = asyncio.run(
            exercise_engine_application_service.generate_for_user(
                db=db,
                user_id=user_id,
                vocabulary_ids=vocabulary_ids,
                size=size,
                mode=mode,
            )
        )
        return response.model_dump()

    except Exception as exc:
        logger.exception(
            "generate_exercises_for_user failed for user=%s mode=%s size=%s",
            user_id,
            mode,
            size,
        )
        raise self.retry(exc=exc)
    finally:
        db.close()
