"""Centralized environment-based settings for the agent service."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    SERVER_PORT: int = 30000
    PROJECT_NAME: str = "superset-agent-service"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "local"

    SECRET_KEY: str = Field(default="change-me-in-env")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    DATABASE_URL: str = "sqlite+aiosqlite:///./superset_agent_service.db"

    SUPERSET_MCP_URL: str | None = None
    SUPERSET_MCP_TOKEN: str | None = None

    DEFAULT_MODEL_PROVIDER: str = "openai"
    DEFAULT_MODEL_NAME: str = "gpt-4.1-mini"

    MAX_AGENT_STEPS: int = 12
    MAX_RUN_SECONDS: int = 120
    MAX_SQL_ROWS: int = 1000

    @field_validator("SUPERSET_MCP_URL", mode="before")
    @classmethod
    def empty_mcp_url_is_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
