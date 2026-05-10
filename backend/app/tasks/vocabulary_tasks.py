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
    from app.core.db import SessionLocal
    from app.modules.vocabulary.repository import VocabularyRepository
    from app.modules.vocabulary.schemas import VocabularyItemRead
    from app.modules.vocabulary.service.items import VocabularyService

    with SessionLocal() as db:
        try:
            service = VocabularyService(VocabularyRepository(db))
            item = asyncio.run(
                service.create_item_with_ai(
                    user_id=user_id,
                    english_lemma=english_lemma,
                    russian_translation=russian_translation,
                    source_sentence=source_sentence,
                    source_url=source_url,
                )
            )
            return VocabularyItemRead.model_validate(item, from_attributes=True).model_dump()
        except Exception as exc:
            logger.exception("add_word_with_ai failed for user=%s lemma=%s", user_id, english_lemma)
            raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="vocabulary.capture_to_vocabulary",
    max_retries=2,
    default_retry_delay=5,
)
def capture_to_vocabulary_task(
    self,
    *,
    user_id: int,
    selected_text: str,
    source_url: str | None,
    source_sentence: str | None,
    force_new_vocabulary_item: bool,
) -> dict:
    from app.core.db import SessionLocal
    from app.modules.vocabulary.repository import VocabularyRepository
    from app.modules.vocabulary.schemas import VocabularyFromCaptureResponse, VocabularyItemRead
    from app.modules.vocabulary.service.items import VocabularyService

    with SessionLocal() as db:
        try:
            service = VocabularyService(VocabularyRepository(db))
            result, _ = asyncio.run(
                service.capture_to_vocabulary(
                    user_id=user_id,
                    selected_text=selected_text,
                    source_url=source_url,
                    source_sentence=source_sentence,
                    force_new_vocabulary_item=force_new_vocabulary_item,
                )
            )
            return VocabularyFromCaptureResponse(
                vocabulary=VocabularyItemRead.model_validate(result, from_attributes=True),
            ).model_dump()
        except Exception as exc:
            logger.exception(
                "capture_to_vocabulary failed for user=%s text=%s",
                user_id, selected_text,
            )
            raise self.retry(exc=exc)
