from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.training.schemas import ExerciseDTO

logger = logging.getLogger(__name__)

_MAX_BUFFER = 10
_REFILL_SIZE = 8
_LOW_WATERMARK = 5
_TTL_SECONDS = 3600  # буфер живёт 1 час без обращений
_REFILL_LOCK_TTL = 120  # лок на пополнение — 2 минуты


def _buffer_key(user_id: int, mode: str) -> str:
    return f"exercise_buffer:{user_id}:{mode}"


def _refill_lock_key(user_id: int, mode: str) -> str:
    return f"exercise_buffer_refilling:{user_id}:{mode}"


def _dto_to_dict(exercise) -> dict:
    try:
        return asdict(exercise)
    except TypeError:
        return {
            "prompt": exercise.prompt,
            "answer": exercise.answer,
            "exercise_type": exercise.exercise_type,
            "target_word": exercise.target_word,
            "options": list(exercise.options),
            "topic_cluster_key": getattr(exercise, "topic_cluster_key", None),
            "topic_display_name": getattr(exercise, "topic_display_name", None),
        }


class ExercisePrefetchService:
    def __init__(self) -> None:
        self._redis = None
        self._redis_checked = False
        # Fallback: in-memory буфер если Redis недоступен
        self._mem_queue: dict[tuple[int, str], list[dict]] = {}
        self._mem_refilling: set[tuple[int, str]] = set()

    def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        try:
            from redis import Redis
            from app.core.config import get_settings
            self._redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
            self._redis.ping()
        except Exception:
            logger.warning("Redis unavailable for prefetch buffer — falling back to in-memory")
            self._redis = None
        return self._redis

    # ── Redis-backed операции ──────────────────────────────────────────────

    def _redis_buffer_size(self, r, user_id: int, mode: str) -> int:
        return r.llen(_buffer_key(user_id, mode))

    def _redis_get(self, r, user_id: int, mode: str, count: int) -> list[dict]:
        key = _buffer_key(user_id, mode)
        pipe = r.pipeline()
        for _ in range(count):
            pipe.lpop(key)
        results = pipe.execute()
        items = []
        for raw in results:
            if raw is None:
                break
            try:
                items.append(json.loads(raw))
            except Exception:
                pass
        if items:
            r.expire(key, _TTL_SECONDS)
        return items

    def _redis_store(self, r, user_id: int, mode: str, exercises: list) -> None:
        key = _buffer_key(user_id, mode)
        current = r.llen(key)
        can_add = max(0, _MAX_BUFFER - current)
        if can_add == 0:
            return
        pipe = r.pipeline()
        for ex in exercises[:can_add]:
            pipe.rpush(key, json.dumps(_dto_to_dict(ex)))
        pipe.expire(key, _TTL_SECONDS)
        pipe.execute()

    def _redis_is_refilling(self, r, user_id: int, mode: str) -> bool:
        return bool(r.exists(_refill_lock_key(user_id, mode)))

    def _redis_set_refilling(self, r, user_id: int, mode: str) -> bool:
        """SET NX — атомарно ставим лок. Возвращает True если лок получен."""
        return bool(r.set(_refill_lock_key(user_id, mode), "1", nx=True, ex=_REFILL_LOCK_TTL))

    def _redis_clear_refilling(self, r, user_id: int, mode: str) -> None:
        r.delete(_refill_lock_key(user_id, mode))

    def _redis_clear_refilling_safe(self, user_id: int, mode: str) -> None:
        """Сброс лока без исключений — вызывается из Celery при ошибке."""
        r = self._get_redis()
        if r:
            try:
                r.delete(_refill_lock_key(user_id, mode))
            except Exception:
                pass
        self._mem_refilling.discard((user_id, mode))

    # ── Публичный API ──────────────────────────────────────────────────────

    def has_prefetch(self, user_id: int, mode: str) -> bool:
        r = self._get_redis()
        if r:
            try:
                return self._redis_buffer_size(r, user_id, mode) > 0
            except Exception:
                pass
        key = (user_id, mode)
        return bool(self._mem_queue.get(key))

    def buffer_size(self, user_id: int, mode: str) -> int:
        r = self._get_redis()
        if r:
            try:
                return self._redis_buffer_size(r, user_id, mode)
            except Exception:
                pass
        return len(self._mem_queue.get((user_id, mode), []))

    def get_prefetched(self, user_id: int, mode: str, count: int) -> list:
        r = self._get_redis()
        if r:
            try:
                raw_items = self._redis_get(r, user_id, mode, count)
                from app.modules.training.schemas import ExerciseDTO
                return [
                    ExerciseDTO(
                        prompt=item["prompt"],
                        answer=item["answer"],
                        exercise_type=item["exercise_type"],
                        target_word=item.get("target_word"),
                        options=item.get("options", []),
                        topic_cluster_key=item.get("topic_cluster_key"),
                        topic_display_name=item.get("topic_display_name"),
                    )
                    for item in raw_items
                ]
            except Exception:
                logger.exception("Redis get_prefetched failed")

        # Fallback in-memory
        key = (user_id, mode)
        items = self._mem_queue.get(key, [])
        taken, remaining = items[:count], items[count:]
        if remaining:
            self._mem_queue[key] = remaining
        else:
            self._mem_queue.pop(key, None)
        from app.modules.training.schemas import ExerciseDTO
        return [
            ExerciseDTO(
                prompt=item["prompt"],
                answer=item["answer"],
                exercise_type=item["exercise_type"],
                target_word=item.get("target_word"),
                options=item.get("options", []),
                topic_cluster_key=item.get("topic_cluster_key"),
                topic_display_name=item.get("topic_display_name"),
            )
            for item in taken
        ]

    def store_prefetch(self, user_id: int, mode: str, exercises: list) -> None:
        r = self._get_redis()
        if r:
            try:
                self._redis_store(r, user_id, mode, exercises)
                self._redis_clear_refilling(r, user_id, mode)
                return
            except Exception:
                logger.exception("Redis store_prefetch failed")

        # Fallback in-memory
        key = (user_id, mode)
        existing = self._mem_queue.get(key, [])
        combined = existing + [_dto_to_dict(e) for e in exercises]
        self._mem_queue[key] = combined[:_MAX_BUFFER]
        self._mem_refilling.discard(key)

    def clear_prefetch(self, user_id: int, mode: str | None = None) -> None:
        r = self._get_redis()
        modes = [mode] if mode else ["sentence_translation_full", "word_scramble", "word_definition_match"]
        for m in modes:
            if r:
                try:
                    r.delete(_buffer_key(user_id, m))
                    r.delete(_refill_lock_key(user_id, m))
                except Exception:
                    pass
            key = (user_id, m)
            self._mem_queue.pop(key, None)
            self._mem_refilling.discard(key)

    def trigger_refill_if_needed(self, user_id: int, mode: str, vocab_size: int = 1) -> bool:
        """Запускает Celery-задачу пополнения если буфер ниже watermark и словарь не пуст."""
        if vocab_size <= 0:
            return False

        current = self.buffer_size(user_id, mode)
        if current >= _LOW_WATERMARK:
            return False

        needed = _MAX_BUFFER - current
        r = self._get_redis()

        if r:
            try:
                if not self._redis_set_refilling(r, user_id, mode):
                    return False  # уже пополняется
            except Exception:
                pass
        else:
            key = (user_id, mode)
            if key in self._mem_refilling:
                return False
            self._mem_refilling.add(key)

        try:
            from app.celery_app import enqueue_task
            from app.tasks.exercise_tasks import refill_exercise_buffer
            enqueue_task(
                refill_exercise_buffer,
                owner_user_id=user_id,
                kwargs={
                    "user_id": user_id,
                    "mode": mode,
                    "size": needed,
                },
            )
            logger.debug("Prefetch refill triggered: user=%s mode=%s needed=%s", user_id, mode, needed)
            return True
        except Exception:
            if r:
                try:
                    self._redis_clear_refilling(r, user_id, mode)
                except Exception:
                    pass
            else:
                self._mem_refilling.discard((user_id, mode))
            logger.exception("Failed to trigger prefetch refill for user=%s mode=%s", user_id, mode)
            return False


prefetch_service = ExercisePrefetchService()
