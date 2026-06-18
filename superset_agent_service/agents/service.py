"""Application service that coordinates agent runs and runtime execution.

协调 Agent 运行记录与 Runtime 执行过程的应用服务。
"""

from collections.abc import Awaitable, Callable
from uuid import uuid4

from superset_agent_service.agents.runtime import LangGraphRuntime
from superset_agent_service.agents.schemas import AgentRequest, AgentResponse
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.runs.service import RunService
from superset_agent_service.tools.registry import ToolRegistry


class AgentService:
    """Assemble Agent dependencies and manage one complete request lifecycle.

    组装 Agent 所需依赖，并管理一次完整请求的生命周期。
    """

    def __init__(
        self,
        event_sink: Callable[[dict[str, object]], Awaitable[None]] | None = None,
    ) -> None:
        """Create services that share the same optional live-event sink.

        创建共享同一个可选实时事件接收器的服务对象。
        """

        self.runs = RunService(event_sink=event_sink)
        self.tools = ToolRegistry.default()
        self.runtime = LangGraphRuntime(tools=self.tools, runs=self.runs)

    async def chat(
        self, request: AgentRequest, context: PermissionContext
    ) -> AgentResponse:
        """Execute one request and keep its run status consistent.

        执行一次请求，并确保其运行状态始终保持一致。
        """

        run_id = str(uuid4())
        self.runs.bind_run(run_id=run_id, user_id=context.user_id)
        await self.runs.start_run(request=request, context=context)

        try:
            answer = await self.runtime.invoke(request=request, context=context)
            await self.runs.complete_run(status="completed", final_answer=answer)
            return AgentResponse(run_id=run_id, answer=answer, status="completed")
        except Exception as exc:
            # Record failure before re-raising so observability is never lost.
            # 重新抛出异常前先记录失败，避免丢失可观测信息。
            await self.runs.fail_run(error=str(exc))
            raise
