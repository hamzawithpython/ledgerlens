"""Application settings, loaded from environment / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str
    database_url: str
    confidence_threshold: float = 0.85
    extraction_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — reads .env once."""
    return Settings()