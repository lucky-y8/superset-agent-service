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
    LOG_LEVEL: str = "INFO"

    # Comma-separated browser origins allowed to call the public Agent API.
    # 允许调用对外 Agent API 的浏览器来源，多个域名使用英文逗号分隔。
    CORS_ALLOWED_ORIGINS: str = "http://127.0.0.1:9000,http://localhost:9000"
    # Keep the powerful MCP debug console disabled on public deployments.
    # 对外部署时默认关闭具备底层 MCP 调试能力的 Debug 页面。
    ENABLE_DEBUG_UI: bool = False
    # The read-only Usage page can be enabled independently in production.
    # 生产环境可以单独开启只读 Usage 页面，其数据接口仍要求管理员 Token。
    ENABLE_USAGE_UI: bool = False
    # Query-string tokens are convenient locally but can leak through URL logs.
    # 查询参数 Token 便于本地调试，但可能通过 URL 日志泄露，生产环境应关闭。
    ALLOW_WEBSOCKET_QUERY_TOKEN: bool = True

    SECRET_KEY: str = Field(default="change-me-in-env")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    DATABASE_URL: str = "sqlite+aiosqlite:///./superset_agent_service.db"
    # Reserved for the upcoming distributed cache and task queue integration.
    # 为后续分布式缓存和任务队列接入预留；当前业务代码尚未使用 Redis。
    REDIS_URL: str | None = None

    SUPERSET_MCP_URL: str | None = None
    SUPERSET_MCP_TOKEN: str | None = None

    # Superset token verification endpoint used by production Agent requests.
    # 生产环境 Agent 请求使用的 Superset Token 校验接口地址。
    SUPERSET_AGENT_TOKEN_VERIFY_URL: str | None = None
    # Optional service-to-service secret sent only from Agent Service to Superset.
    # Agent Service 调 Superset 校验接口时使用的可选服务间密钥。
    SUPERSET_AGENT_SERVICE_KEY: str | None = None
    # Cache successful verification results briefly to protect Superset from
    # repeated checks during one active chat while keeping revocation reasonably fresh.
    # 短暂缓存校验成功的结果，减少同一轮对话反复请求 Superset，同时让权限回收仍能较快生效。
    AGENT_TOKEN_VERIFY_CACHE_SECONDS: int = 60
    # Delegate business tool authorization to Superset MCP. The Agent service
    # still verifies tokens and runs safety guards, but it no longer treats
    # allowed_tools from the token verifier as the final MCP tool allow-list.
    # 将业务工具权限委托给 Superset MCP。Agent 服务仍校验 Token 并执行安全护栏，但不再把
    # Token 验证接口返回的 allowed_tools 当作最终 MCP 工具白名单。
    AGENT_DELEGATE_AUTH_TO_MCP: bool = True

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
    # When enabled, creation tasks ask the user for required choices before
    # calling Superset tools. It is disabled by default to preserve automation.
    # 开启后，创建类任务会先引导用户补全必要选择，再调用 Superset 工具；默认关闭以保留自动执行体验。
    AGENT_GUIDED_MODE: bool = False

    # Retrieval Augmented Generation configuration.
    # RAG（检索增强生成）相关配置。
    RAG_ENABLED: bool = False
    RAG_TOP_K: int = 5
    RAG_CHUNK_SIZE: int = 900
    RAG_CHUNK_OVERLAP: int = 120

    EMBEDDING_PROVIDER: str = "dashscope"
    EMBEDDING_MODEL: str = "text-embedding-v4"
    EMBEDDING_DIM: int = 1024
    DASHSCOPE_API_KEY: str | None = None
    DASHSCOPE_EMBEDDING_URL: str = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    )

    QDRANT_URL: str = "http://127.0.0.1:6333"
    QDRANT_COLLECTION: str = "superset_agent_knowledge"
    QDRANT_MEMORY_COLLECTION: str = "superset_agent_memory"
    QDRANT_API_KEY: str | None = None
    SEMANTIC_MEMORY_TOP_K: int = 5

    OSS_REGION: str | None = None
    OSS_ENDPOINT: str | None = None
    OSS_BUCKET: str | None = None
    OSS_ACCESS_KEY_ID: str | None = None
    OSS_ACCESS_KEY_SECRET: str | None = None
    OSS_PREFIX: str = "superset-agent-knowledge"

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Return normalized origins for Starlette CORS middleware.

        返回供 Starlette CORS 中间件使用的规范化来源列表。
        """

        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @field_validator("SUPERSET_MCP_URL", mode="before")
    @classmethod
    def empty_mcp_url_is_none(cls, value: str | None) -> str | None:
        """Normalize an empty MCP URL so optional configuration works correctly.

        将空的 MCP URL 归一化为 None，确保可选配置判断正确。
        """

        if value == "":
            return None
        return value

    @field_validator("SUPERSET_AGENT_TOKEN_VERIFY_URL", mode="before")
    @classmethod
    def empty_agent_verify_url_is_none(cls, value: str | None) -> str | None:
        """Normalize an empty token verification URL to disabled production auth.

        将空的 Token 校验地址归一化为 None，表示未开启生产认证接入。
        """

        if value == "":
            return None
        return value

    @field_validator("SUPERSET_AGENT_SERVICE_KEY", mode="before")
    @classmethod
    def empty_agent_service_key_is_none(cls, value: str | None) -> str | None:
        """Treat an empty service key as missing optional service authentication.

        将空服务密钥视为未配置，避免发送无意义的空请求头。
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
