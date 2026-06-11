"""Administrative endpoints for reading runtime configuration.

用于读取运行时配置的管理接口。
"""

from fastapi import APIRouter

from superset_agent_service.admin.schemas import RuntimeConfig
from superset_agent_service.config import settings

router = APIRouter()


@router.get("/runtime-config", response_model=RuntimeConfig)
async def get_runtime_config() -> RuntimeConfig:
    """Expose the non-secret Runtime settings needed by an admin UI.

    向管理界面提供不含敏感信息的 Runtime 配置。
    """

    return RuntimeConfig(
        default_model_provider=settings.DEFAULT_MODEL_PROVIDER,
        default_model_name=settings.DEFAULT_MODEL_NAME,
        max_agent_steps=settings.MAX_AGENT_STEPS,
        max_run_seconds=settings.MAX_RUN_SECONDS,
    )
