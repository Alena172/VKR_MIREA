from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, читаемые из `.env` и переменных окружения."""

    app_name: str = "VKR English Learning API"
    database_url: str = Field(min_length=1)
    bootstrap_schema_on_startup: bool = True
    ai_provider: str = Field(default="stub", min_length=1)
    ai_base_url: str = Field(min_length=1)
    ai_model: str = Field(min_length=1)
    ai_timeout_seconds: float = Field(default=20.0, gt=0)
    ai_max_retries: int = Field(default=1, ge=0)
    translation_strict_remote: bool = True
    jwt_secret: str = Field(min_length=32)
    jwt_issuer: str = Field(min_length=1)
    jwt_access_ttl_minutes: int = Field(default=60 * 24, gt=0)
    cors_allow_origins: str = Field(min_length=1)
    cors_allow_origin_regex: str | None = r"^(chrome-extension://[a-p]{32}|moz-extension://.+)$"
    trusted_hosts: str = Field(min_length=1)
    # Celery / Redis
    redis_url: str = Field(min_length=1)
    celery_broker_url: str = Field(min_length=1)
    celery_result_backend: str = Field(min_length=1)
    # LibreTranslate
    libretranslate_url: str = Field(min_length=1)
    libretranslate_api_key: str = ""
    libretranslate_timeout_seconds: float = Field(default=10.0, gt=0)
    libretranslate_enabled: bool = True
    scrypt_n: int = Field(default=4096, ge=2**10)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_allow_origins_list(self) -> list[str]:
        """Преобразует CSV-строку CORS origin-ов в список для middleware."""

        values = [item.strip() for item in self.cors_allow_origins.split(",")]
        return [item for item in values if item]

    @property
    def trusted_hosts_list(self) -> list[str]:
        """Преобразует CSV-строку доверенных хостов в список для middleware."""

        values = [item.strip() for item in self.trusted_hosts.split(",")]
        return [item for item in values if item]


@lru_cache
def get_settings() -> Settings:
    """Возвращает кэшированный объект настроек приложения."""

    return Settings()
