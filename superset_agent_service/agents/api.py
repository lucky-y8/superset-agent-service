"""HTTP endpoints for agent chat and future agent operations."""

from fastapi import APIRouter, Depends

from superset_agent_service.agents.schemas import AgentRequest, AgentResponse
from superset_agent_service.agents.service import AgentService
from superset_agent_service.auth.dependencies import get_permission_context
from superset_agent_service.auth.schemas import PermissionContext

router = APIRouter()


@router.post("/chat", response_model=AgentResponse)
async def chat(
    request: AgentRequest,
    context: PermissionContext = Depends(get_permission_context),
) -> AgentResponse:
    service = AgentService()
    return await service.chat(request=request, context=context)
