"""Celery application factory with a lightweight local fallback.

Import this module to get the configured Celery instance.
Tasks are auto-discovered from app.tasks.* when Celery is installed.
In test environments without Celery, tasks still expose `.delay(...)`
and store in-memory results that can be polled through `/tasks/{task_id}`.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings

_LOCAL_TASK_RESULTS: dict[str, dict[str, Any]] = {}
_LOCAL_TASK_OWNERS: dict[str, dict[str, Any]] = {}
CELERY_AVAILABLE = True
_TASK_TTL_SECONDS = 3600

try:
    from celery import Celery
except ModuleNotFoundError:
    CELERY_AVAILABLE = False
    Celery = None  # type: ignore[assignment]

try:
    from redis import Redis
except ModuleNotFoundError:
    Redis = None  # type: ignore[assignment]


@dataclass
class LocalTaskResult:
    id: str


class LocalTaskContext:
    def retry(self, *, exc: Exception, **_: Any) -> None:
        raise exc


class LocalTaskWrapper:
    def __init__(self, fn, *, bind: bool) -> None:
        self._fn = fn
        self._bind = bind

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self._bind:
            return self._fn(LocalTaskContext(), *args, **kwargs)
        return self._fn(*args, **kwargs)

    def apply_async(
        self,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
        **_: Any,
    ) -> LocalTaskResult:
        call_args = args or ()
        call_kwargs = kwargs or {}
        task_id = str(uuid.uuid4())
        _store_local_task_result(task_id, {"status": "STARTED", "result": None, "error": None})
        try:
            result = self(*call_args, **call_kwargs)
            _store_local_task_result(task_id, {"status": "SUCCESS", "result": result, "error": None})
        except Exception as exc:
            _store_local_task_result(task_id, {"status": "FAILURE", "result": None, "error": str(exc)})
        return LocalTaskResult(id=task_id)

    def delay(self, *args: Any, **kwargs: Any) -> LocalTaskResult:
        return self.apply_async(args=args, kwargs=kwargs)


class LocalCeleryApp:
    def task(self, *decorator_args: Any, **decorator_kwargs: Any):
        bind = bool(decorator_kwargs.get("bind", False))

        def decorator(fn):
            return LocalTaskWrapper(fn, bind=bind)

        return decorator


def _now_timestamp() -> float:
    return time.time()


def _is_expired(expires_at: float | None) -> bool:
    return expires_at is not None and expires_at <= _now_timestamp()


def _prune_local_task_results() -> None:
    expired_task_ids = [
        task_id
        for task_id, payload in _LOCAL_TASK_RESULTS.items()
        if _is_expired(payload.get("expires_at"))
    ]
    for task_id in expired_task_ids:
        _LOCAL_TASK_RESULTS.pop(task_id, None)


def _prune_local_task_owners() -> None:
    expired_task_ids = [
        task_id
        for task_id, payload in _LOCAL_TASK_OWNERS.items()
        if _is_expired(payload.get("expires_at"))
    ]
    for task_id in expired_task_ids:
        _LOCAL_TASK_OWNERS.pop(task_id, None)


def _store_local_task_result(task_id: str, payload: dict[str, Any]) -> None:
    _prune_local_task_results()
    _LOCAL_TASK_RESULTS[task_id] = {
        **payload,
        "expires_at": _now_timestamp() + _TASK_TTL_SECONDS,
    }


def _register_local_task_owner(task_id: str, owner_user_id: int) -> None:
    _prune_local_task_owners()
    _LOCAL_TASK_OWNERS[task_id] = {
        "owner_user_id": owner_user_id,
        "expires_at": _now_timestamp() + _TASK_TTL_SECONDS,
    }


def _get_local_task_owner(task_id: str) -> int | None:
    _prune_local_task_owners()
    payload = _LOCAL_TASK_OWNERS.get(task_id)
    if payload is None:
        return None
    owner_user_id = payload.get("owner_user_id")
    return owner_user_id if isinstance(owner_user_id, int) else None


class TaskOwnershipRegistry:
    def __init__(self) -> None:
        self._redis_client: Redis | None = None
        self._redis_checked = False

    def _get_redis_client(self) -> Redis | None:
        if self._redis_checked:
            return self._redis_client
        self._redis_checked = True
        if Redis is None:
            return None
        settings = get_settings()
        try:
            self._redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            self._redis_client = None
        return self._redis_client

    def register(self, *, task_id: str, owner_user_id: int) -> None:
        redis_client = self._get_redis_client()
        if redis_client is not None:
            try:
                redis_client.setex(
                    f"task-owner:{task_id}",
                    _TASK_TTL_SECONDS,
                    str(owner_user_id),
                )
                return
            except Exception:
                pass
        _register_local_task_owner(task_id, owner_user_id)

    def get_owner_user_id(self, task_id: str) -> int | None:
        redis_client = self._get_redis_client()
        if redis_client is not None:
            try:
                value = redis_client.get(f"task-owner:{task_id}")
                if value is not None:
                    return int(value)
            except Exception:
                pass
        return _get_local_task_owner(task_id)


task_ownership_registry = TaskOwnershipRegistry()


def enqueue_task(task: Any, *, owner_user_id: int, kwargs: dict[str, Any]) -> Any:
    async_result = task.apply_async(kwargs=kwargs)
    task_ownership_registry.register(task_id=async_result.id, owner_user_id=owner_user_id)
    return async_result


def create_celery():
    if not CELERY_AVAILABLE:
        return LocalCeleryApp()

    settings = get_settings()
    app = Celery(
        "vkr_worker",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=[
            "app.tasks.vocabulary_tasks",
            "app.tasks.exercise_tasks",
        ],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        result_expires=3600,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = create_celery()
