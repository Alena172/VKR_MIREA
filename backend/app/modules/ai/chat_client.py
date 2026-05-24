"""Низкоуровневый HTTP-клиент для OpenAI-совместимого AI backend."""

from __future__ import annotations

import logging

import httpx

_log = logging.getLogger(__name__)


class AIChatClient:
    """HTTP-клиент для AI-провайдера с OpenAI-совместимым API."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, int(max_retries))
        self._async_client: httpx.AsyncClient | None = None

    @property
    def model(self) -> str:
        """Имя текущей модели, передаваемое провайдеру."""
        return self._model

    @property
    def base_url(self) -> str:
        """Базовый URL AI-провайдера без завершающего `/`."""
        return self._base_url

    @property
    def timeout_seconds(self) -> float:
        """Таймаут одного HTTP-запроса к AI-провайдеру."""
        return self._timeout_seconds

    @property
    def max_retries(self) -> int:
        """Максимальное число повторных попыток для временных сетевых ошибок."""
        return self._max_retries

    def remote_enabled(self) -> bool:
        """Показывает, достаточно ли настроек для удалённого вызова AI API."""
        return bool(self._base_url) and bool(self._model)

    def _get_async_client(self) -> httpx.AsyncClient:
        """Лениво создаёт и переиспользует `httpx.AsyncClient`."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self._timeout_seconds,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._async_client

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 300,
    ) -> str | None:
        """Отправляет один chat completion запрос и возвращает только текст ответа."""
        if not self.remote_enabled():
            return None

        payload = {
            "model": self._model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        client = self._get_async_client()
        url = f"{self._base_url}/chat/completions"

        for attempt in range(self._max_retries + 1):
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                ) or None
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                _log.warning("AI request HTTP %d on attempt %d: %s", status, attempt + 1, url)
                if status < 500:
                    # 4xx — не повторяем, модель/ключ/запрос некорректны
                    break
            except httpx.TimeoutException:
                _log.warning("AI request timed out on attempt %d: %s", attempt + 1, url)
            except Exception as exc:
                _log.warning("AI request failed on attempt %d: %s — %s", attempt + 1, url, exc)
        return None
