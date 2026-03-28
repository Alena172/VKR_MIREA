from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.core.application import AsyncTaskResponse, application_access
from app.modules.ai_services.contracts import ExerciseSeed, GenerateExercisesRequest
from app.modules.ai_services.service import TranslationProviderUnavailableError, ai_service
from app.modules.context_memory.public_api import context_memory_public_api
from app.modules.exercise_engine.assembler import (
    to_exercise_generate_result_dto,
    to_exercise_item_dto,
)
from app.modules.exercise_engine.contracts import ExerciseGenerateResultDTO, ExerciseItemDTO
from app.modules.exercise_engine.prefetch_service import prefetch_service
from app.modules.exercise_engine.schemas import ExerciseGenerateRequest
from app.modules.learning_graph.public_api import learning_graph_public_api
from app.modules.vocabulary.public_api import vocabulary_public_api


class ExerciseEngineApplicationService:
    _PREFETCH_EXTRA = 5
    _BATCH_SIZE = 5

    def queue_generation(
        self,
        *,
        db: Session,
        payload: ExerciseGenerateRequest,
        current_user_id: int,
    ) -> AsyncTaskResponse:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=payload.user_id,
            current_user_id=current_user_id,
        )
        application_access.ensure_user_exists(db=db, user_id=target_user_id)

        from app.tasks.exercise_tasks import generate_exercises_for_user

        task = generate_exercises_for_user.delay(
            user_id=target_user_id,
            vocabulary_ids=payload.vocabulary_ids or [],
            size=payload.size,
            mode=payload.mode,
        )
        return AsyncTaskResponse(task_id=task.id)

    async def generate_for_user(
        self,
        *,
        db: Session,
        user_id: int,
        vocabulary_ids: list[int],
        size: int,
        mode: str,
    ) -> ExerciseGenerateResultDTO:
        user = application_access.get_user_or_404(db=db, user_id=user_id)
        use_prefetch = not vocabulary_ids

        prefetched: list[ExerciseItemDTO] = []
        if use_prefetch and prefetch_service.has_prefetch(user_id, mode):
            prefetched = prefetch_service.get_prefetched(user_id, mode, size)
            if len(prefetched) >= size:
                return to_exercise_generate_result_dto(
                    exercises=prefetched[:size],
                    note="Prefetched exercises used",
                )

        vocabulary_items = self._resolve_vocabulary_items(
            db=db,
            user_id=user_id,
            vocabulary_ids=vocabulary_ids,
            mode=mode,
        )
        cefr_level = context_memory_public_api.get_effective_cefr_dto(
            db=db,
            user_id=user_id,
            fallback_cefr=user.cefr_level,
        ).cefr_level

        required_count = size - len(prefetched)
        generation_target = required_count + (self._PREFETCH_EXTRA if use_prefetch else 0)
        seeds, anchors_used_count = self._build_seeds(
            db=db,
            user_id=user_id,
            vocabulary_items=vocabulary_items,
        )
        generated_items, provider_note = await self._generate_items(
            seeds=seeds,
            size=generation_target,
            mode=mode,
            cefr_level=cefr_level,
        )

        immediate_items = prefetched + generated_items[:required_count]
        if use_prefetch:
            extra_items = generated_items[required_count:]
            if extra_items:
                prefetch_service.store_prefetch(user_id, mode, extra_items)

        note_prefix = "Prefetched + " if prefetched else ""
        return to_exercise_generate_result_dto(
            exercises=immediate_items[:size],
            note=f"{note_prefix}{provider_note}; graph_anchors_used={anchors_used_count}",
        )

    def _resolve_vocabulary_items(
        self,
        *,
        db: Session,
        user_id: int,
        vocabulary_ids: list[int],
        mode: str,
    ):
        vocabulary_items = vocabulary_public_api.list_items(db, user_id=user_id)
        if vocabulary_ids:
            allowed = set(vocabulary_ids)
            vocabulary_items = [item for item in vocabulary_items if item.id in allowed]
        vocabulary_items = self._dedupe_vocabulary_by_lemma(vocabulary_items)

        if not vocabulary_items:
            raise ValueError("Vocabulary is empty. Add words before generating exercises.")

        if mode == "word_definition_match":
            unique_lemmas = {item.english_lemma.strip().lower() for item in vocabulary_items if item.english_lemma}
            if len(unique_lemmas) < 4:
                raise ValueError("Need at least 4 different words in vocabulary for definition matching.")
        return vocabulary_items

    def _dedupe_vocabulary_by_lemma(self, vocabulary_items):
        deduped: dict[str, object] = {}
        for item in vocabulary_items:
            key = item.english_lemma.strip().lower()
            if not key or key in deduped:
                continue
            deduped[key] = item
        return list(deduped.values())

    def _build_seeds(
        self,
        *,
        db: Session,
        user_id: int,
        vocabulary_items,
    ) -> tuple[list[ExerciseSeed], int]:
        anchors_used_count = 0
        seeds: list[ExerciseSeed] = []
        for item in vocabulary_items:
            source_sentence = item.source_sentence
            anchors = learning_graph_public_api.list_word_anchors(
                db=db,
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
                    source_sentence=source_sentence,
                )
            )

        if len(seeds) > 1:
            randomizer = secrets.SystemRandom()
            randomizer.shuffle(seeds)

        return seeds, anchors_used_count

    async def _generate_items(
        self,
        *,
        seeds: list[ExerciseSeed],
        size: int,
        mode: str,
        cefr_level: str,
    ) -> tuple[list[ExerciseItemDTO], str]:
        if size > self._BATCH_SIZE and len(seeds) >= self._BATCH_SIZE:
            batches = []
            remaining = size
            batch_idx = 0
            while remaining > 0:
                batch_count = min(self._BATCH_SIZE, remaining)
                batch_seeds = []
                for i in range(min(self._BATCH_SIZE, len(seeds))):
                    seed_idx = (batch_idx * self._BATCH_SIZE + i) % len(seeds)
                    batch_seeds.append(seeds[seed_idx])
                batches.append(
                    GenerateExercisesRequest(
                        size=batch_count,
                        cefr_level=cefr_level,
                        mode=mode,
                        seeds=batch_seeds,
                    )
                )
                remaining -= batch_count
                batch_idx += 1

            try:
                batch_responses = await ai_service.generate_exercises_batch(batches)
            except TranslationProviderUnavailableError as exc:
                raise RuntimeError(str(exc)) from exc

            all_items: list[ExerciseItemDTO] = []
            for response in batch_responses:
                all_items.extend(
                    [
                        to_exercise_item_dto(
                            prompt=item.prompt,
                            answer=item.answer,
                            exercise_type=item.exercise_type,
                            options=item.options,
                        )
                        for item in response.exercises
                    ]
                )
            return all_items[:size], f"AI batch generation used (batches={len(batches)})"

        try:
            response = await ai_service.generate_exercises_async(
                GenerateExercisesRequest(size=size, cefr_level=cefr_level, mode=mode, seeds=seeds)
            )
        except TranslationProviderUnavailableError as exc:
            raise RuntimeError(str(exc)) from exc

        items = [
            to_exercise_item_dto(
                prompt=item.prompt,
                answer=item.answer,
                exercise_type=item.exercise_type,
                options=item.options,
            )
            for item in response.exercises
        ]
        return items, f"AI generation used ({response.provider_note})"


exercise_engine_application_service = ExerciseEngineApplicationService()
