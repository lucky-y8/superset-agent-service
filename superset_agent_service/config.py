"""Centralized environment-based settings for the agent service.

Agent 服务基于环境变量的集中配置。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Validate and expose all process-level application settings.

    校验并提供当前进程使用的全部应用配置。
    """

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

    # DeepSeek exposes an OpenAI-compatible chat-completions API.  Keeping
    # these names provider-neutral lets the Runtime switch to another
    # compatible model later without changing application code.
    # DeepSeek 提供 OpenAI 兼容的聊天补全接口。使用与厂商无关的配置名称，
    # 以后切换其他兼容模型时便无需修改应用代码。
    OPENAI_BASE_URL: str = "https://api.deepseek.com"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "deepseek-chat"

    MAX_AGENT_STEPS: int = 12
    MAX_RUN_SECONDS: int = 120
    MAX_SQL_ROWS: int = 1000

    @field_validator("SUPERSET_MCP_URL", mode="before")
    @classmethod
    def empty_mcp_url_is_none(cls, value: str | None) -> str | None:
        """Normalize an empty MCP URL so optional configuration works correctly.

        将空的 MCP URL 归一化为 None，确保可选配置判断正确。
        """

        if value == "":
            return None
        return value

    @field_validator("OPENAI_API_KEY", mode="before")
    @classmethod
    def empty_api_key_is_none(cls, value: str | None) -> str | None:
        """Treat an empty .env value as missing configuration.

        将 .env 中的空值视为未配置。
        """

        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Build settings once and reuse them throughout the process.

    只构建一次配置对象，并在整个进程中复用。
    """

    return Settings()


settings = get_settings()
