"""Health check endpoint used by local development and deployment probes."""

from fastapi import APIRouter

from superset_agent_service.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.PROJECT_NAME}
