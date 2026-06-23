"""Top-level API router that mounts all versioned feature routers.

挂载全部版本化功能路由的顶层 API 路由器。
"""

from fastapi import APIRouter

from superset_agent_service.admin.api import router as admin_router
from superset_agent_service.agents.api import router as agents_router
from superset_agent_service.api.health import router as health_router
from superset_agent_service.memory.api import router as memory_router
from superset_agent_service.rag.api import router as rag_router
from superset_agent_service.runs.api import router as runs_router
from superset_agent_service.tools.api import router as mcp_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(runs_router, prefix="/runs", tags=["runs"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(mcp_router, prefix="/mcp", tags=["mcp-development"])
api_router.include_router(rag_router, prefix="/rag", tags=["rag"])
api_router.include_router(memory_router, prefix="/memories", tags=["memories"])
