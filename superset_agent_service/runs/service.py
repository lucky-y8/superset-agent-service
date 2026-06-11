"""In-memory run trace service used until database persistence is added.

在接入数据库持久化之前使用的内存运行轨迹服务。
"""

from collections.abc import Awaitable, Callable

from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.runs.schemas import RunEvent, RunTrace

RunEventSink = Callable[[dict[str, object]], Awaitable[None]]


class RunService:
    """Store run events and optionally publish them to a live client.

    保存运行事件，并可选择将其实时推送给客户端。
    """

    _store: dict[str, RunTrace] = {}

    def __init__(self, event_sink: RunEventSink | None = None) -> None:
        """Create an unbound run service with an optional event publisher.

        创建尚未绑定具体运行、并带有可选事件发布器的服务。
        """

        self.run_id: str | None = None
        self.user_id: str | None = None
        self.event_sink = event_sink

    def bind_run(self, run_id: str, user_id: str) -> None:
        """Bind this service instance to a newly created run trace.

        将当前服务实例绑定到一条新创建的运行轨迹。
        """

        self.run_id = run_id
        self.user_id = user_id
        self._store[run_id] = RunTrace(run_id=run_id, user_id=user_id, status="created")

    async def start_run(
        self, request: AgentRequest, context: PermissionContext
    ) -> None:
        """Record the initial request information for the bound run.

        记录当前运行的初始请求信息。
        """

        await self.record_event(
            event_type="run_started",
            payload={"user_id": context.user_id, "question": request.question},
        )

    async def complete_run(self, status: str = "completed") -> None:
        """Mark the current run as completed and emit its final event.

        将当前运行标记为完成，并发送结束事件。
        """

        self._current().status = status
        await self.record_event(event_type="run_completed")

    async def fail_run(self, error: str) -> None:
        """Mark the current run as failed and preserve the error message.

        将当前运行标记为失败，并保存错误信息。
        """

        self._current().status = "failed"
        await self.record_event(event_type="run_failed", payload={"error": error})

    async def record_event(
        self, event_type: str, payload: dict[str, object] | None = None
    ) -> None:
        """Persist one event in memory and publish it to live listeners.

        在内存中保存一条事件，并将其推送给实时监听者。
        """

        event = RunEvent(event_type=event_type, payload=payload or {})
        self._current().events.append(event)
        await self._publish(event_type="run_event", event=event)

    async def publish_transient(
        self,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        """Push a live-only event without storing it in the final RunTrace.

        推送一条仅用于实时展示、不会写入最终 RunTrace 的事件。

        Token deltas are intentionally transient. Persisting every token would
        make traces noisy and expensive, while WebSocket clients still receive
        them immediately for a fluid response.

        Token 增量被特意设计为临时事件。保存每个 Token 会让轨迹冗长且成本较高，
        而 WebSocket 客户端仍可立即收到它们，从而实现流畅的回答展示。
        """

        await self._publish(
            event_type=event_type,
            payload=payload or {},
        )

    @classmethod
    def get_trace(cls, run_id: str) -> RunTrace | None:
        """Look up a run trace from the process-local store.

        从当前进程的本地存储中查询运行轨迹。
        """

        return cls._store.get(run_id)

    def _current(self) -> RunTrace:
        """Return the bound trace and fail fast when no run is active.

        返回当前绑定的轨迹；没有活动运行时立即报错。
        """

        if not self.run_id or self.run_id not in self._store:
            raise RuntimeError("No active run is bound")
        return self._store[self.run_id]

    async def _publish(
        self,
        event_type: str,
        event: RunEvent | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        """Build the WebSocket event envelope and send it when configured.

        构造 WebSocket 事件信封，并在已配置接收器时发送。
        """

        if self.event_sink is None:
            return

        message: dict[str, object] = {
            "type": event_type,
            "run_id": self.run_id or "",
        }
        if event is not None:
            message["event"] = event.model_dump(mode="json")
        if payload is not None:
            message["payload"] = payload
        await self.event_sink(message)
