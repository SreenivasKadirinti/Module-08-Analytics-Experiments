from functools import lru_cache
from urllib.parse import quote_plus
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",   # extra keys in .env (e.g. TEST_DATABASE_URL) won't crash startup
    )

    APP_NAME: str = "Module 08 - Analytics Backend"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    DATABASE_HOST: str
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    API_KEY: Optional[str] = None
    ANALYST_API_KEY: Optional[str] = None
    ADMIN_API_KEY: Optional[str] = None

    @property
    def DATABASE_URL(self) -> str:
        # quote_plus keeps passwords with @ # / : from breaking the URL
        return (
            f"postgresql+psycopg://{quote_plus(self.DATABASE_USER)}:"
            f"{quote_plus(self.DATABASE_PASSWORD)}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings()