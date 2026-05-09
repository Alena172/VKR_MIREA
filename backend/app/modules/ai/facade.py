from __future__ import annotations

import asyncio
from collections import deque

from app.core.config import get_settings
from app.modules.ai.chat_client import AIChatClient
from app.modules.ai.schemas import (
    AIStatusResponse,
    ExplainErrorRequest,
    ExplainErrorResponse,
    GenerateExercisesRequest,
    GenerateExercisesResponse,
)
from app.modules.ai.service.definitions import DefinitionService
from app.modules.ai.service.exercises import ExerciseGenerator, _extract_json_payload


class AIProviderUnavailableError(RuntimeError):
    """AI-провайдер недоступен или не сконфигурирован."""


class AIFacade:
    """Единая точка входа к AI для всех доменных модулей."""

    def __init__(self) -> None:
        settings = get_settings()
        self._chat_client = AIChatClient(
            base_url=settings.ai_base_url,
            model=settings.ai_model,
            timeout_seconds=settings.ai_timeout_seconds,
            max_retries=max(0, int(settings.ai_max_retries)),
        )
        self._recent_sentences: dict[str, deque[str]] = {}
        self._definition_service = DefinitionService(
            chat_complete_async=self._chat_completion_async,
        )
        self._exercise_generator = ExerciseGenerator(
            model=self._chat_client.model,
            max_retries=self._chat_client.max_retries,
            remote_enabled=self._chat_client.remote_enabled,
            chat_complete_async=self._chat_completion_async,
            provider_unavailable_error=AIProviderUnavailableError,
            recent_sentences=self._recent_sentences,
        )

    def is_remote_enabled(self) -> bool:
        return self._chat_client.remote_enabled()

    def _run_sync(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError("Synchronous AIFacade methods cannot be called from an active event loop")

    async def _chat_completion_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 300,
    ) -> str | None:
        return await self._chat_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def get_status(self) -> AIStatusResponse:
        return AIStatusResponse(
            model=self._chat_client.model,
            remote_enabled=self._chat_client.remote_enabled(),
            base_url=self._chat_client.base_url,
            timeout_seconds=self._chat_client.timeout_seconds,
            max_retries=self._chat_client.max_retries,
        )

    def _fallback_explain_error(self) -> ExplainErrorResponse:
        return ExplainErrorResponse(
            explanation_ru=(
                "Ответ отличается от ожидаемого. Проверь форму слова, порядок слов "
                "и значение в контексте предложения."
            )
        )

    def _fallback_improvement_hint(self) -> ExplainErrorResponse:
        return ExplainErrorResponse(
            explanation_ru=(
                "Перевод засчитан как верный. Можно улучшить стиль: выбрать более нейтральную "
                "формулировку и терминологию ближе к учебному контексту."
            )
        )

    def explain_error(self, payload: ExplainErrorRequest) -> ExplainErrorResponse:
        return self._run_sync(self.explain_error_async(payload))

    async def explain_error_async(self, payload: ExplainErrorRequest) -> ExplainErrorResponse:
        content = await self._chat_completion_async(
            system_prompt=(
                "Ты преподаватель английского для русскоязычных пользователей. "
                "Давай короткое и понятное объяснение ошибки на русском."
            ),
            user_prompt=(
                f"Задание: {payload.english_prompt}\n"
                f"Ожидался ответ: {payload.expected_answer}\n"
                f"Ответ пользователя: {payload.user_answer}\n"
                "Сформулируй объяснение ошибки в 1-2 предложениях."
            ),
            temperature=0.1,
            max_tokens=180,
        )
        if content:
            return ExplainErrorResponse(explanation_ru=content)
        return self._fallback_explain_error()

    def suggest_improvement(self, payload: ExplainErrorRequest) -> ExplainErrorResponse:
        return self._run_sync(self.suggest_improvement_async(payload))

    async def suggest_improvement_async(self, payload: ExplainErrorRequest) -> ExplainErrorResponse:
        content = await self._chat_completion_async(
            system_prompt=(
                "Ты преподаватель английского для русскоязычных пользователей. "
                "Ответ пользователя уже считается правильным. "
                "Дай мягкую и краткую рекомендацию по стилю перевода на русском, без слова 'ошибка'."
            ),
            user_prompt=(
                f"Задание: {payload.english_prompt}\n"
                f"Ожидаемый вариант: {payload.expected_answer}\n"
                f"Вариант пользователя: {payload.user_answer}\n"
                "Сформулируй рекомендацию в 1-2 предложениях."
            ),
            temperature=0.1,
            max_tokens=180,
        )
        if content:
            return ExplainErrorResponse(explanation_ru=content)
        return self._fallback_improvement_hint()

    def is_translation_semantically_correct(
        self,
        *,
        english_prompt: str,
        expected_answer: str,
        user_answer: str,
    ) -> bool:
        return self._run_sync(
            self.is_translation_semantically_correct_async(
                english_prompt=english_prompt,
                expected_answer=expected_answer,
                user_answer=user_answer,
            )
        )

    async def is_translation_semantically_correct_async(
        self,
        *,
        english_prompt: str,
        expected_answer: str,
        user_answer: str,
    ) -> bool:
        content = await self._chat_completion_async(
            system_prompt=(
                "Ты проверяешь переводы с английского на русский. "
                "Если пользовательский перевод передает тот же основной смысл, считай его правильным, "
                "даже если стиль неидеален или слова отличаются. "
                "Незначительные стилистические огрехи не делают ответ неправильным. "
                'Верни только JSON: {"equivalent": true|false}.'
            ),
            user_prompt=(
                f"Исходное задание: {english_prompt}\n"
                f"Эталонный перевод: {expected_answer}\n"
                f"Перевод пользователя: {user_answer}\n"
                "Сравни смысл."
            ),
            temperature=0.0,
            max_tokens=60,
        )
        if content:
            payload = _extract_json_payload(content)
            if isinstance(payload, dict) and isinstance(payload.get("equivalent"), bool):
                return payload["equivalent"]
            lowered = content.lower()
            if "true" in lowered:
                return True
            if "false" in lowered:
                return False
        return False

    def generate_context_definition(
        self,
        *,
        english_lemma: str,
        russian_translation: str,
        source_sentence: str | None,
        cefr_level: str | None = None,
    ) -> str:
        return self._run_sync(
            self._definition_service.generate_context_definition_async(
                english_lemma=english_lemma,
                russian_translation=russian_translation,
                source_sentence=source_sentence,
                cefr_level=cefr_level,
            )
        )

    async def generate_context_definition_async(
        self,
        *,
        english_lemma: str,
        russian_translation: str,
        source_sentence: str | None,
        cefr_level: str | None = None,
    ) -> str:
        return await self._definition_service.generate_context_definition_async(
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            source_sentence=source_sentence,
            cefr_level=cefr_level,
        )

    def generate_context_definition_fast(
        self,
        *,
        english_lemma: str,
        russian_translation: str,
        source_sentence: str | None,
    ) -> str:
        return self._definition_service.generate_context_definition_fast(
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            source_sentence=source_sentence,
        )

    def generate_exercises(self, payload: GenerateExercisesRequest) -> GenerateExercisesResponse:
        return self._run_sync(self.generate_exercises_async(payload))

    async def generate_exercises_async(self, payload: GenerateExercisesRequest) -> GenerateExercisesResponse:
        return await self._exercise_generator.generate_exercises_async(payload)

    async def generate_exercises_batch(
        self,
        batches: list[GenerateExercisesRequest],
    ) -> list[GenerateExercisesResponse]:
        return await self._exercise_generator.generate_exercises_batch(batches)


ai_facade = AIFacade()
