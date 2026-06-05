"""Top-level API router that mounts all versioned feature routers."""

from fastapi import APIRouter

from superset_agent_service.admin.api import router as admin_router
from superset_agent_service.agents.api import router as agents_router
from superset_agent_service.api.health import router as health_router
from superset_agent_service.runs.api import router as runs_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(runs_router, prefix="/runs", tags=["runs"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
