"""Сервис генерации упражнений и управления предзагруженным буфером заданий."""

from __future__ import annotations

import secrets

from fastapi import Depends

from app.celery_app import enqueue_task
from app.core.application import AsyncTaskResponse
from app.modules.ai.schemas import ExerciseSeed
from app.modules.graph.repository import GraphRepository
from app.modules.graph.service.graph import GraphService
from app.modules.identity.service import IdentityService
from app.modules.training.schemas import (
    ExerciseDTO,
    ExerciseGenerateRequest,
    ExerciseGenerateResultDTO,
)
from app.modules.training.service.exercise_builder import exercise_builder
from app.modules.training.service.prefetch import prefetch_service
from app.modules.vocabulary.service.items import VocabularyService

_PREFETCH_EXTRA = 3  # сколько лишних упражнений генерировать сверх запроса при синхронном пути


class TrainingService:
    """Оркестрирует генерацию упражнений из словаря, графа тем и AI-провайдера."""

    def __init__(
        self,
        identity_service: IdentityService = Depends(),
        vocab_service: VocabularyService = Depends(),
        graph_service: GraphService = Depends(),
    ) -> None:
        self._identity_service = identity_service
        self._vocab_service = vocab_service
        self._graph_service = graph_service

    def _get_user_or_404(self, user_id: int):
        """Короткий прокси к identity-сервису для единообразной обработки `404`."""
        return self._identity_service.get_user_or_404(user_id=user_id)

    def queue_generation(
        self,
        *,
        payload: ExerciseGenerateRequest,
        current_user_id: int,
    ) -> AsyncTaskResponse:
        """Ставит генерацию упражнений в очередь и возвращает идентификатор задачи."""
        from app.core.application import application_access
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=payload.user_id,
            current_user_id=current_user_id,
        )
        self._get_user_or_404(target_user_id)

        from app.tasks.exercise_tasks import generate_exercises_for_user

        task = enqueue_task(
            generate_exercises_for_user,
            owner_user_id=current_user_id,
            kwargs={
                "user_id": target_user_id,
                "vocabulary_ids": payload.vocabulary_ids or [],
                "size": payload.size,
                "mode": payload.mode,
                "fast_start": payload.fast_start,
                "incremental": payload.incremental,
            },
        )
        return AsyncTaskResponse(task_id=task.id)

    async def generate_for_user(
        self,
        *,
        user_id: int,
        vocabulary_ids: list[int],
        size: int,
        mode: str,
        fast_start: bool = False,
        incremental: bool = False,
    ) -> ExerciseGenerateResultDTO:
        """Генерирует упражнения синхронно, при необходимости используя и пополняя prefetch-буфер."""
        user = self._get_user_or_404(user_id)
        use_prefetch = not vocabulary_ids and mode == "sentence_translation_full"

        prefetched: list[ExerciseDTO] = []
        if use_prefetch and prefetch_service.has_prefetch(user_id, mode):
            prefetched = prefetch_service.get_prefetched(user_id, mode, size)

        # Проверяем есть ли слова в словаре — без них Celery-задача упадёт с ValueError
        vocab_size = self._vocab_service.count_user_items(user_id=user_id) if use_prefetch else 0

        # Incremental: отдаём буфер немедленно, пополнение запускается автоматически через watermark
        if incremental:
            if use_prefetch:
                prefetch_service.trigger_refill_if_needed(user_id, mode, vocab_size=vocab_size)
            return ExerciseGenerateResultDTO(
                exercises=prefetched,
                note=f"incremental; buffer_used={len(prefetched)}",
            )

        if len(prefetched) >= size:
            # Буфер выдан — запускаем пополнение если нужно
            if use_prefetch:
                prefetch_service.trigger_refill_if_needed(user_id, mode, vocab_size=vocab_size)
            return ExerciseGenerateResultDTO(
                exercises=prefetched[:size],
                note="prefetched_full",
            )

        vocabulary_items = self._resolve_vocabulary_items(
            user_id=user_id,
            vocabulary_ids=vocabulary_ids,
            mode=mode,
        )
        required_count = size - len(prefetched)
        # При синхронной генерации сразу кладём немного лишнего в буфер
        server_prefetch_extra = _PREFETCH_EXTRA if use_prefetch and not fast_start else 0
        generation_target = required_count + server_prefetch_extra
        seeds = self._build_seeds(user_id=user_id, vocabulary_items=vocabulary_items)
        generated_items, provider_note = await exercise_builder.build_items(
            seeds=seeds,
            size=generation_target,
            mode=mode,
            cefr_level=user.cefr_level,
            fast_start=fast_start,
        )

        immediate_items = prefetched + generated_items[:required_count]
        if use_prefetch:
            extra_items = generated_items[required_count:]
            if extra_items:
                prefetch_service.store_prefetch(user_id, mode, extra_items)
            # После сохранения — проверяем нужно ли ещё пополнять
            prefetch_service.trigger_refill_if_needed(user_id, mode, vocab_size=len(vocabulary_items))

        note_prefix = "prefetched_partial + " if prefetched else ""
        fast_start_note = "fast_start; " if fast_start else ""
        return ExerciseGenerateResultDTO(
            exercises=immediate_items[:size],
            note=f"{note_prefix}{fast_start_note}{provider_note}",
        )

    def _resolve_vocabulary_items(
        self,
        *,
        user_id: int,
        vocabulary_ids: list[int],
        mode: str,
    ):
        """Подготавливает подходящий набор слов для выбранного режима упражнений."""
        vocabulary_items = self._vocab_service.list_user_items(user_id=user_id)
        if vocabulary_ids:
            allowed = set(vocabulary_ids)
            vocabulary_items = [item for item in vocabulary_items if item.id in allowed]
        if not vocabulary_items:
            raise ValueError("Vocabulary is empty. Add words before generating exercises.")

        if mode in {"word_definition_match", "word_scramble"}:
            # Для этих режимов берем один смысл на лемму, иначе в подборке окажутся два "book".
            vocabulary_items = _dedupe_vocabulary_by_lemma(vocabulary_items)

        if mode == "word_definition_match":
            vocabulary_items = [
                item for item in vocabulary_items
                if (item.context_definition_ru or "").strip()
            ]
            unique_lemmas = {item.english_lemma.strip().lower() for item in vocabulary_items if item.english_lemma}
            if len(unique_lemmas) < 4:
                raise ValueError("Need at least 4 different words with saved definitions for definition matching.")
        return vocabulary_items

    def _build_seeds(self, *, user_id: int, vocabulary_items) -> list[ExerciseSeed]:
        """Преобразует словарные элементы в seed-объекты для exercise builder."""
        saved_lemmas = {item.english_lemma.strip().lower() for item in vocabulary_items if item.english_lemma}
        interest_words = self._graph_service.get_interest_words(
            limit=30,
            current_user_id=user_id,
            saved_lemmas=saved_lemmas,
        )
        # Индекс: display_name кластера → слова из общего словаря в этом кластере
        by_signal: dict[str, list] = {}
        for w in interest_words.items:
            by_signal.setdefault(w.primary_signal, []).append(w)

        rng = secrets.SystemRandom()
        seeds = []
        for item in vocabulary_items:
            cluster_hint: str | None = None
            # Ищем hint из того же кластера (по display_name кластера)
            # topic_cluster_key → display_name берём из GraphRepository._TOPIC_MARKERS,
            # но проще — ищем по ключу напрямую через interest_words
            if item.topic_cluster_key:
                display_name = GraphRepository._TOPIC_MARKERS.get(item.topic_cluster_key, (item.topic_cluster_key,))[0]
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
        return seeds


def _dedupe_vocabulary_by_lemma(vocabulary_items):
    """Оставляет по одному словарному элементу на лемму для режимов без омонимии."""
    deduped: dict[str, object] = {}
    for item in vocabulary_items:
        key = item.english_lemma.strip().lower()
        if not key or key in deduped:
            continue
        deduped[key] = item
    return list(deduped.values())
