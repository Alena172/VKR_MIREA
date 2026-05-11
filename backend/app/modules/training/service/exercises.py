from __future__ import annotations

import secrets

from fastapi import Depends

from app.celery_app import enqueue_task
from app.core.application import AsyncTaskResponse
from app.modules.ai.schemas import ExerciseSeed
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

_PREFETCH_EXTRA = 5


class TrainingService:
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
        return self._identity_service.get_user_or_404(user_id=user_id)

    def queue_generation(
        self,
        *,
        payload: ExerciseGenerateRequest,
        current_user_id: int,
    ) -> AsyncTaskResponse:
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
        user = self._get_user_or_404(user_id)
        use_prefetch = not vocabulary_ids

        prefetched: list[ExerciseDTO] = []
        if use_prefetch and prefetch_service.has_prefetch(user_id, mode):
            prefetched = prefetch_service.get_prefetched(user_id, mode, size)
            if len(prefetched) >= size:
                return ExerciseGenerateResultDTO(
                    exercises=prefetched[:size],
                    note="Prefetched exercises used",
                )

        vocabulary_items = self._resolve_vocabulary_items(
            user_id=user_id,
            vocabulary_ids=vocabulary_ids,
            mode=mode,
        )
        required_count = size - len(prefetched)
        server_prefetch_extra = _PREFETCH_EXTRA if use_prefetch and not fast_start and not incremental else 0
        generation_target = required_count + server_prefetch_extra
        seeds, anchors_used_count = self._build_seeds(user_id=user_id, vocabulary_items=vocabulary_items)
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

        note_prefix = "Prefetched + " if prefetched else ""
        fast_start_note = "fast_start; " if fast_start else ""
        incremental_note = "incremental; " if incremental else ""
        return ExerciseGenerateResultDTO(
            exercises=immediate_items[:size],
            note=f"{note_prefix}{fast_start_note}{incremental_note}{provider_note}; semantic_context_used={anchors_used_count}",
        )

    def _resolve_vocabulary_items(
        self,
        *,
        user_id: int,
        vocabulary_ids: list[int],
        mode: str,
    ):
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

    def _build_seeds(
        self,
        *,
        user_id: int,
        vocabulary_items,
    ) -> tuple[list[ExerciseSeed], int]:
        anchors_used_count = 0
        seeds: list[ExerciseSeed] = []
        for item in vocabulary_items:
            source_sentence = item.source_sentence
            anchors = self._graph_service.list_word_anchors(
                user_id=user_id,
                english_lemma=item.english_lemma,
                limit=3,
            )
            if anchors:
                anchor_words = [anchor.english_lemma for anchor in anchors if anchor.english_lemma]
                if anchor_words:
                    anchors_used_count += 1
                    anchor_hint = "Related known words: " + ", ".join(anchor_words) + "."
                    source_sentence = f"{source_sentence or ''} {anchor_hint}".strip()

            seeds.append(
                ExerciseSeed(
                    english_lemma=item.english_lemma,
                    russian_translation=item.russian_translation,
                    context_definition_ru=item.context_definition_ru,
                    source_sentence=source_sentence,
                )
            )

        if len(seeds) > 1:
            secrets.SystemRandom().shuffle(seeds)

        return seeds, anchors_used_count


def _dedupe_vocabulary_by_lemma(vocabulary_items):
    deduped: dict[str, object] = {}
    for item in vocabulary_items:
        key = item.english_lemma.strip().lower()
        if not key or key in deduped:
            continue
        deduped[key] = item
    return list(deduped.values())
