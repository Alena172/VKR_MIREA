"""Celery tasks for vocabulary operations.

These tasks offload slow AI calls (context definition generation,
translation) from the HTTP request cycle so the user gets an
immediate response and the heavy work happens in the background.
"""
from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="vocabulary.add_word_with_ai",
    max_retries=2,
    default_retry_delay=5,
)
def add_word_with_ai(
    self,
    *,
    user_id: int,
    english_lemma: str,
    russian_translation: str,
    source_sentence: str | None,
    source_url: str | None,
) -> dict:
    """Create a vocabulary item with AI-generated context definition.

    Returns a dict that matches the VocabularyItem schema so the
    frontend can use it directly after polling.
    """
    from app.core.db import SessionLocal
    from app.modules.vocabulary.application_service import vocabulary_application_service

    db = SessionLocal()
    try:
        item = asyncio.run(
            vocabulary_application_service.create_item_with_ai(
                db=db,
                user_id=user_id,
                english_lemma=english_lemma,
                russian_translation=russian_translation,
                source_sentence=source_sentence,
                source_url=source_url,
            )
        )
        return item.model_dump()
    except Exception as exc:
        logger.exception("add_word_with_ai failed for user=%s lemma=%s", user_id, english_lemma)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="vocabulary.study_flow_capture_to_vocabulary",
    max_retries=2,
    default_retry_delay=5,
)
def study_flow_capture_to_vocabulary(
    self,
    *,
    user_id: int,
    selected_text: str,
    source_url: str | None,
    source_sentence: str | None,
    force_new_vocabulary_item: bool,
) -> dict:
    """Run the full study-flow capture-to-vocabulary pipeline in a worker.

    Returns a dict matching CaptureToVocabularyResponse schema.
    """
    from app.core.db import SessionLocal
    from app.modules.vocabulary.application_service import vocabulary_application_service

    db = SessionLocal()
    try:
        result = asyncio.run(
            vocabulary_application_service.capture_to_vocabulary(
                db=db,
                user_id=user_id,
                selected_text=selected_text,
                source_url=source_url,
                source_sentence=source_sentence,
                force_new_vocabulary_item=force_new_vocabulary_item,
            )
        )
        return result.model_dump()
    except Exception as exc:
        logger.exception(
            "study_flow_capture_to_vocabulary failed for user=%s text=%s",
            user_id,
            selected_text,
        )
        raise self.retry(exc=exc)
    finally:
        db.close()
