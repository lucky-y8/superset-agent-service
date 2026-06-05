"""Runtime boundary for the future LangGraph agent workflow."""

from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.runs.service import RunService
from superset_agent_service.tools.registry import ToolRegistry


class LangGraphRuntime:
    """Thin boundary around the future LangGraph workflow."""

    def __init__(self, tools: ToolRegistry, runs: RunService):
        self.tools = tools
        self.runs = runs

    async def invoke(self, request: AgentRequest, context: PermissionContext) -> str:
        await self.runs.record_event(
            event_type="plan",
            payload={
                "question": request.question,
                "dashboard_id": request.dashboard_id,
                "chart_id": request.chart_id,
            },
        )
        return (
            "Agent runtime scaffold is ready. Next step: connect Superset MCP "
            "tools and replace this placeholder with a LangGraph workflow."
        )
