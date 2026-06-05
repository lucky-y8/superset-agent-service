"""Administrative endpoints for reading runtime configuration."""

from fastapi import APIRouter

from superset_agent_service.admin.schemas import RuntimeConfig
from superset_agent_service.config import settings

router = APIRouter()


@router.get("/runtime-config", response_model=RuntimeConfig)
async def get_runtime_config() -> RuntimeConfig:
    return RuntimeConfig(
        default_model_provider=settings.DEFAULT_MODEL_PROVIDER,
        default_model_name=settings.DEFAULT_MODEL_NAME,
        max_agent_steps=settings.MAX_AGENT_STEPS,
        max_run_seconds=settings.MAX_RUN_SECONDS,
    )
