from functools import lru_cache
from typing import Annotated

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AadeshSmart API"
    database_url: PostgresDsn = "postgresql+psycopg://postgres:postgres@localhost:5432/aadeshsmart"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    log_level: str = "INFO"
    sarvam_mode: str = "mock"
    sarvam_api_key: str | None = None
    sarvam_timeout_seconds: float = Field(default=45, gt=0)
    gemini_mode: str = "mock"
    google_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_seconds: float = Field(default=45, gt=0)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("sarvam_mode", "gemini_mode")
    @classmethod
    def validate_provider_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"mock", "live"}:
            raise ValueError("Provider mode must be 'mock' or 'live'")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
