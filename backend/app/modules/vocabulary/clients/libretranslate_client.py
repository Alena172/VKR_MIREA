from __future__ import annotations

import asyncio
import re

import httpx

_RE_RU = re.compile(r"[а-яёА-ЯЁ]+")


class LibreTranslateClient:
    """HTTP-клиент к LibreTranslate (EN→RU)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._async_client: httpx.AsyncClient | None = None

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self._timeout,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
            )
        return self._async_client

    def _build_payload(self, text: str) -> dict:
        payload: dict = {"q": text, "source": "en", "target": "ru", "format": "text"}
        if self._api_key:
            payload["api_key"] = self._api_key
        return payload

    async def _post(self, text: str) -> str | None:
        try:
            client = self._get_async_client()
            response = await client.post(
                f"{self._base_url}/translate",
                json=self._build_payload(text),
            )
            if response.status_code != 200:
                return None
            data = response.json()
            return data.get("translatedText") or None
        except Exception:
            return None

    async def translate_word(self, word: str) -> str | None:
        result = await self._post(word.strip().lower())
        return result.strip() if result else None

    async def translate_word_in_context(
        self,
        word: str,
        sentence: str,
        all_normal_forms_fn: object = None,
    ) -> str | None:
        """Переводит слово с учётом контекста предложения.

        Два параллельных запроса: слово отдельно + предложение целиком.
        Шаг 1: базовый перевод слова (по леммам) присутствует в переводе
                предложения — контекст подтверждает, возвращаем его.
        Шаг 1б: однокоренное слово (общий префикс ≥4 букв) найдено в переводе
                предложения — возвращаем его (напр. книга→забронировать не найдёт,
                но бегать→работает тоже не найдёт → None → уходит в AI).
        Если ни один шаг не сработал — возвращаем None, запрос уходит в AI.
        """
        word_ru_raw, sent_ru_raw = await asyncio.gather(
            self._post(word.strip().lower()),
            self._post(sentence.strip()),
        )

        if not word_ru_raw:
            return None
        word_ru = word_ru_raw.strip()
        if not sent_ru_raw:
            return word_ru

        sent_ru = sent_ru_raw.strip()
        ru_tokens_all = _RE_RU.findall(sent_ru.lower())

        if all_normal_forms_fn is not None:
            # Шаг 1: лемма базового перевода есть в переводе предложения
            word_forms = all_normal_forms_fn(word_ru)
            if any(all_normal_forms_fn(t) & word_forms for t in ru_tokens_all):
                return word_ru

            # Шаг 1б: однокоренное слово (общий префикс ≥4 букв)
            word_root = word_ru[:4] if len(word_ru) >= 4 else word_ru
            root_matches = [t for t in ru_tokens_all if len(t) >= 4 and t[:4] == word_root]
            if root_matches:
                return root_matches[0]

        # Контекстный перевод не определён офлайн — передаём в AI
        return None
