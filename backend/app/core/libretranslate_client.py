from __future__ import annotations

import httpx


class LibreTranslateClient:
    """HTTP-клиент для LibreTranslate API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or ""
        self._timeout_seconds = timeout_seconds
        self._async_client: httpx.AsyncClient | None = None

    def is_configured(self) -> bool:
        return bool(self._base_url)

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self._timeout_seconds,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._async_client

    async def translate(
        self,
        *,
        text: str,
        source_lang: str = "en",
        target_lang: str = "ru",
        context: str | None = None,
    ) -> str | None:
        if not self.is_configured():
            return None

        payload: dict = {
            "q": text,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
        }
        if self._api_key:
            payload["api_key"] = self._api_key
        if context:
            payload["context"] = context

        try:
            client = self._get_async_client()
            response = await client.post(
                f"{self._base_url}/translate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("translatedText", "").strip()
            return result or None
        except Exception:
            return None
