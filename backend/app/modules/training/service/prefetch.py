from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.training.schemas import ExerciseDTO


class ExercisePrefetchService:
    def __init__(self) -> None:
        self._queue: dict[tuple[int, str], list[ExerciseDTO]] = {}
        self._max_prefetch_per_user = 10

    def has_prefetch(self, user_id: int, mode: str) -> bool:
        key = (user_id, mode)
        return key in self._queue and len(self._queue[key]) > 0

    def get_prefetched(self, user_id: int, mode: str, count: int) -> list[ExerciseDTO]:
        key = (user_id, mode)
        if key not in self._queue:
            return []
        exercises = self._queue[key][:count]
        self._queue[key] = self._queue[key][count:]
        if not self._queue[key]:
            del self._queue[key]
        return exercises

    def store_prefetch(self, user_id: int, mode: str, exercises: list[ExerciseDTO]) -> None:
        key = (user_id, mode)
        if key not in self._queue:
            self._queue[key] = []
        self._queue[key].extend(exercises)
        self._queue[key] = self._queue[key][:self._max_prefetch_per_user]

    def clear_prefetch(self, user_id: int, mode: str | None = None) -> None:
        if mode is not None:
            key = (user_id, mode)
            if key in self._queue:
                del self._queue[key]
            return
        to_remove = [key for key in self._queue if key[0] == user_id]
        for key in to_remove:
            del self._queue[key]


prefetch_service = ExercisePrefetchService()
