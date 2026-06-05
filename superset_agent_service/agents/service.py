"""Application service that coordinates agent runs and runtime execution."""

from uuid import uuid4

from superset_agent_service.agents.runtime import LangGraphRuntime
from superset_agent_service.agents.schemas import AgentRequest, AgentResponse
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.runs.service import RunService
from superset_agent_service.tools.registry import ToolRegistry


class AgentService:
    def __init__(self) -> None:
        self.runs = RunService()
        self.tools = ToolRegistry.default()
        self.runtime = LangGraphRuntime(tools=self.tools, runs=self.runs)

    async def chat(
        self, request: AgentRequest, context: PermissionContext
    ) -> AgentResponse:
        run_id = str(uuid4())
        self.runs.bind_run(run_id=run_id, user_id=context.user_id)
        await self.runs.start_run(request=request, context=context)

        try:
            answer = await self.runtime.invoke(request=request, context=context)
            await self.runs.complete_run(status="completed")
            return AgentResponse(run_id=run_id, answer=answer, status="completed")
        except Exception as exc:
            await self.runs.fail_run(error=str(exc))
            raise
