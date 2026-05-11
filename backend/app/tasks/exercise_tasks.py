from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _exercise_result_to_dict(result) -> dict:
    return {
        "exercises": [
            {
                "prompt": item.prompt,
                "answer": item.answer,
                "exercise_type": item.exercise_type,
                "target_word": item.target_word,
                "options": list(item.options),
            }
            for item in result.exercises
        ],
        "note": result.note,
    }


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
    fast_start: bool = False,
    incremental: bool = False,
) -> dict:
    from app.core.db import SessionLocal
    from app.modules.graph.repository import GraphRepository
    from app.modules.graph.service.graph import GraphService
    from app.modules.identity.repository import IdentityRepository
    from app.modules.identity.service import IdentityService
    from app.modules.training.service.exercises import TrainingService
    from app.modules.vocabulary.repository import VocabularyRepository
    from app.modules.vocabulary.service.items import VocabularyService

    with SessionLocal() as db:
        try:
            identity_service = IdentityService(IdentityRepository(db))
            service = TrainingService(
                identity_service=identity_service,
                vocab_service=VocabularyService(VocabularyRepository(db)),
                graph_service=GraphService(GraphRepository(db), identity_service),
            )
            response = asyncio.run(
                service.generate_for_user(
                    user_id=user_id,
                    vocabulary_ids=vocabulary_ids,
                    size=size,
                    mode=mode,
                    fast_start=fast_start,
                    incremental=incremental,
                )
            )
            return _exercise_result_to_dict(response)
        except Exception as exc:
            logger.exception(
                "generate_exercises_for_user failed for user=%s mode=%s size=%s",
                user_id, mode, size,
            )
            raise self.retry(exc=exc)
