from __future__ import annotations

import asyncio
from collections import deque

from app.core.config import get_settings
from app.modules.ai.chat_client import AIChatClient
from app.modules.ai.libretranslate_client import LibreTranslateClient
from app.modules.ai.schemas import (
    AIStatusResponse,
    ExerciseSeed,
    TranslateWithContextRequest,
    TranslateWithContextResponse,
)
from app.modules.ai.service.definitions import DefinitionService
from app.modules.ai.service.exercises import ExerciseMaterialService, _extract_json_payload
from app.modules.ai.service.translation import TranslationService


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
        libretranslate_client = (
            LibreTranslateClient(
                base_url=settings.libretranslate_url,
                api_key=settings.libretranslate_api_key,
                timeout_seconds=settings.libretranslate_timeout_seconds,
            )
            if settings.libretranslate_enabled
            else None
        )
        self._translation_service = TranslationService(
            model=self._chat_client.model,
            translation_strict_remote=settings.translation_strict_remote,
            remote_enabled=self._chat_client.remote_enabled,
            chat_complete_async=self._chat_completion_async,
            provider_unavailable_error=AIProviderUnavailableError,
            libretranslate_client=libretranslate_client,
        )
        self._definition_service = DefinitionService(
            chat_complete_async=self._chat_completion_async,
        )
        self._exercise_materials = ExerciseMaterialService(
            max_retries=self._chat_client.max_retries,
            remote_enabled=self._chat_client.remote_enabled,
            chat_complete_async=self._chat_completion_async,
            provider_unavailable_error=AIProviderUnavailableError,
            translation_service=self._translation_service,
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
                "Ты строгий проверяющий переводов с английского на русский.\n"
                "Твоя задача: определить, передаёт ли перевод пользователя тот же смысл, что и исходное предложение.\n"
                "\n"
                "Правила:\n"
                "- Перевод ПРАВИЛЬНЫЙ если смысл сохранён, даже если использованы другие слова или другой стиль\n"
                "- Перевод НЕПРАВИЛЬНЫЙ если:\n"
                "  * использован антоним ключевого глагола (включить/выключить, открыть/закрыть, прийти/уйти и т.п.)\n"
                "  * пропущено или изменено отрицание (не/нет)\n"
                "  * изменён субъект или объект действия\n"
                "  * смысл действия противоположен оригиналу\n"
                "  * важная часть смысла полностью потеряна\n"
                "- Различия в регистре (ты/вы), порядке слов, стиле — НЕ являются ошибкой\n"
                "\n"
                'Верни только JSON: {"equivalent": true} или {"equivalent": false}. Никаких пояснений.'
            ),
            user_prompt=(
                f"Английское предложение: {english_prompt}\n"
                f"Эталонный перевод: {expected_answer}\n"
                f"Перевод пользователя: {user_answer}\n"
                "\n"
                "Смысл сохранён?"
            ),
            temperature=0.0,
            max_tokens=30,
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
    ) -> str | None:
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
    ) -> str | None:
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
    ) -> str | None:
        return self._definition_service.generate_context_definition_fast(
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            source_sentence=source_sentence,
        )

    def translate_with_context(self, payload: TranslateWithContextRequest) -> TranslateWithContextResponse:
        return self._run_sync(self.translate_with_context_async(payload))

    async def translate_with_context_async(
        self, payload: TranslateWithContextRequest
    ) -> TranslateWithContextResponse:
        return await self._translation_service.translate_with_context_async(payload)

    def fast_translate_single_word(self, text: str) -> str | None:
        return self._translation_service.fast_translate_single_word(text)

    def is_ambiguous_word(self, text: str) -> bool:
        return self._translation_service._looks_ambiguous(text)

    async def translate_phrase_async(self, phrase: str) -> str:
        """Перевод фразы напрямую через LibreTranslate, без глоссария и AI-логики."""
        if self._translation_service._libretranslate is not None:
            result = await self._translation_service._libretranslate.translate_word(phrase)
            if result:
                return result.strip()
        # Fallback: AI без глоссария
        content = await self._chat_completion_async(
            system_prompt="Переведи английскую фразу на русский. Верни только перевод без комментариев.",
            user_prompt=phrase,
            temperature=0.0,
            max_tokens=200,
        )
        if content:
            return content.strip().strip('"')
        return phrase

    async def generate_sentence_pair_async(
        self,
        *,
        seed: ExerciseSeed,
        cefr_level: str,
    ) -> tuple[str, str] | None:
        return await self._exercise_materials.generate_sentence_pair(seed=seed, cefr_level=cefr_level)

    async def build_sentence_for_word_async(
        self,
        *,
        seed: ExerciseSeed,
        cefr_level: str | None = None,
    ) -> str:
        return await self._exercise_materials.build_sentence_for_word(seed=seed, cefr_level=cefr_level)

    async def translate_sentence_for_seed_async(
        self,
        *,
        sentence_en: str,
        seed: ExerciseSeed,
    ) -> str:
        return await self._exercise_materials.translate_sentence_for_seed(sentence_en, seed)


ai_facade = AIFacade()
