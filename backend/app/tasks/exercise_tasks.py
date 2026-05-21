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
        except ValueError as exc:
            logger.warning(
                "generate_exercises_for_user skipped for user=%s mode=%s: %s",
                user_id, mode, exc,
            )
            return {"exercises": [], "note": f"skipped: {exc}"}
        except Exception as exc:
            logger.exception(
                "generate_exercises_for_user failed for user=%s mode=%s size=%s",
                user_id, mode, size,
            )
            raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="exercises.refill_buffer",
    max_retries=1,
    default_retry_delay=5,
)
def refill_exercise_buffer(
    self,
    *,
    user_id: int,
    mode: str,
    size: int,
) -> dict:
    """Генерирует упражнения и сохраняет их напрямую в Redis-буфер.
    Вызывается только из trigger_refill_if_needed."""
    from app.core.db import SessionLocal
    from app.modules.graph.repository import GraphRepository
    from app.modules.graph.service.graph import GraphService
    from app.modules.identity.repository import IdentityRepository
    from app.modules.identity.service import IdentityService
    from app.modules.training.service.exercise_builder import exercise_builder
    from app.modules.training.service.exercises import _dedupe_vocabulary_by_lemma
    from app.modules.training.service.prefetch import prefetch_service
    from app.modules.vocabulary.repository import VocabularyRepository
    from app.modules.vocabulary.service.items import VocabularyService

    with SessionLocal() as db:
        try:
            identity_service = IdentityService(IdentityRepository(db))
            vocab_service = VocabularyService(VocabularyRepository(db))
            graph_service = GraphService(GraphRepository(db), identity_service)

            user = identity_service.get_user_or_404(user_id=user_id)
            vocabulary_items = vocab_service.list_user_items(user_id=user_id)
            if not vocabulary_items:
                raise ValueError("Vocabulary is empty")

            if mode in {"word_definition_match", "word_scramble"}:
                vocabulary_items = _dedupe_vocabulary_by_lemma(vocabulary_items)

            from app.modules.ai.schemas import ExerciseSeed
            import secrets
            from app.modules.graph.repository import GraphRepository as GR

            saved_lemmas = {item.english_lemma.strip().lower() for item in vocabulary_items if item.english_lemma}
            interest_words = graph_service.get_interest_words(
                limit=30,
                current_user_id=user_id,
                saved_lemmas=saved_lemmas,
            )
            by_signal: dict[str, list] = {}
            for w in interest_words.items:
                by_signal.setdefault(w.primary_signal, []).append(w)

            rng = secrets.SystemRandom()
            seeds = []
            for item in vocabulary_items:
                cluster_hint = None
                if item.topic_cluster_key:
                    display_name = GR._TOPIC_MARKERS.get(item.topic_cluster_key, (item.topic_cluster_key,))[0]
                    candidates = by_signal.get(display_name, [])
                    if candidates:
                        chosen = rng.choice(candidates)
                        cluster_hint = f"{chosen.english_lemma} ({chosen.russian_translation})"
                seeds.append(ExerciseSeed(
                    english_lemma=item.english_lemma,
                    russian_translation=item.russian_translation,
                    context_definition_ru=item.context_definition_ru,
                    source_sentence=item.source_sentence,
                    topic_cluster_key=item.topic_cluster_key,
                    cluster_word_hint=cluster_hint,
                ))
            if len(seeds) > 1:
                rng.shuffle(seeds)

            generated_items, note = asyncio.run(exercise_builder.build_items(
                seeds=seeds,
                size=size,
                mode=mode,
                cefr_level=user.cefr_level,
                fast_start=False,
            ))

            if generated_items:
                prefetch_service.store_prefetch(user_id, mode, generated_items)
                logger.info(
                    "refill_exercise_buffer: stored %d exercises for user=%s mode=%s (%s)",
                    len(generated_items), user_id, mode, note,
                )
            else:
                prefetch_service._redis_clear_refilling_safe(user_id, mode)
                logger.warning("refill_exercise_buffer: no exercises generated for user=%s mode=%s", user_id, mode)

            return {"stored": len(generated_items), "note": note}

        except ValueError as exc:
            logger.warning("refill_exercise_buffer skipped for user=%s mode=%s: %s", user_id, mode, exc)
            prefetch_service._redis_clear_refilling_safe(user_id, mode)
            return {"stored": 0, "note": f"skipped: {exc}"}
        except Exception as exc:
            logger.exception("refill_exercise_buffer failed for user=%s mode=%s", user_id, mode)
            prefetch_service._redis_clear_refilling_safe(user_id, mode)
            raise self.retry(exc=exc)
