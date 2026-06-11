"""Health check endpoint used by local development and deployment probes.

供本地开发和部署探针使用的健康检查接口。
"""

from fastapi import APIRouter

from superset_agent_service.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Report that the web process is running and able to serve requests.

    报告 Web 进程正在运行且能够处理请求。
    """

    return {"status": "ok", "service": settings.PROJECT_NAME}
