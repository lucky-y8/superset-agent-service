"""Database-backed service for durable Agent run traces.

使用数据库持久化 Agent 运行轨迹的服务。
"""

from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.db.session import AsyncSessionLocal
from superset_agent_service.runs.models import AgentRunEventModel, AgentRunModel
from superset_agent_service.runs.schemas import RunEvent, RunTrace

RunEventSink = Callable[[dict[str, object]], Awaitable[None]]
SessionFactory = async_sessionmaker[AsyncSession]


class RunService:
    """Persist run events and optionally publish them to a live client.

    持久化运行事件，并可选择将其实时推送给客户端。
    """

    def __init__(
        self,
        event_sink: RunEventSink | None = None,
        session_factory: SessionFactory = AsyncSessionLocal,
    ) -> None:
        """Create an unbound service with database and event dependencies.

        创建尚未绑定具体运行的服务，并注入数据库会话和可选事件发布器。
        """

        self.run_id: str | None = None
        self.user_id: str | None = None
        self.event_sink = event_sink
        self.session_factory = session_factory

    def bind_run(self, run_id: str, user_id: str) -> None:
        """Bind identifiers before the run row is created by ``start_run``.

        在 ``start_run`` 创建数据库记录之前绑定运行标识。
        """

        self.run_id = run_id
        self.user_id = user_id

    async def start_run(
        self, request: AgentRequest, context: PermissionContext
    ) -> None:
        """Create the run and its initial event in one transaction.

        在同一个事务中创建运行记录及其初始事件。
        """

        run_id, user_id = self._require_bound()
        event = RunEvent(
            event_type="run_started",
            payload={"user_id": context.user_id, "question": request.question},
        )
        async with self.session_factory() as session:
            session.add(
                AgentRunModel(
                    run_id=run_id,
                    user_id=user_id,
                    status="created",
                    events=[self._event_model(run_id, event)],
                )
            )
            await session.commit()
        await self._publish(event_type="run_event", event=event)

    async def complete_run(self, status: str = "completed") -> None:
        """Update the run status and persist its final event atomically.

        原子更新运行状态并持久化结束事件。
        """

        await self._set_status_and_record(
            status=status,
            event=RunEvent(event_type="run_completed"),
        )

    async def fail_run(self, error: str) -> None:
        """Mark the run as failed and preserve its error message atomically.

        原子地将运行标记为失败，并保存错误信息。
        """

        await self._set_status_and_record(
            status="failed",
            event=RunEvent(event_type="run_failed", payload={"error": error}),
        )

    async def record_event(
        self, event_type: str, payload: dict[str, object] | None = None
    ) -> None:
        """Persist one event in the database and publish it to live listeners.

        在数据库中保存一条事件，并将其推送给实时监听者。
        """

        run_id, _ = self._require_bound()
        event = RunEvent(event_type=event_type, payload=payload or {})
        async with self.session_factory() as session:
            await self._require_run(session, run_id)
            session.add(self._event_model(run_id, event))
            await session.commit()
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

    @staticmethod
    async def get_trace(
        run_id: str,
        session_factory: SessionFactory = AsyncSessionLocal,
    ) -> RunTrace | None:
        """Load a complete run trace from durable database storage.

        从数据库持久化存储中加载完整运行轨迹。
        """

        async with session_factory() as session:
            statement = (
                select(AgentRunModel)
                .options(selectinload(AgentRunModel.events))
                .where(AgentRunModel.run_id == run_id)
            )
            run = await session.scalar(statement)
            if run is None:
                return None
            return RunTrace(
                run_id=run.run_id,
                user_id=run.user_id,
                status=run.status,
                events=[
                    RunEvent(
                        event_type=event.event_type,
                        payload=event.payload,
                        created_at=event.created_at,
                    )
                    for event in run.events
                ],
            )

    async def _set_status_and_record(self, status: str, event: RunEvent) -> None:
        """Persist a lifecycle status change and its matching event together.

        在同一事务中持久化生命周期状态变化及其对应事件。
        """

        run_id, _ = self._require_bound()
        async with self.session_factory() as session:
            run = await self._require_run(session, run_id)
            run.status = status
            session.add(self._event_model(run_id, event))
            await session.commit()
        await self._publish(event_type="run_event", event=event)

    @staticmethod
    async def _require_run(
        session: AsyncSession,
        run_id: str,
    ) -> AgentRunModel:
        """Load one run row and fail clearly when persistence is inconsistent.

        加载一条运行记录；持久化状态不一致时给出明确错误。
        """

        run = await session.get(AgentRunModel, run_id)
        if run is None:
            raise RuntimeError(f"Run {run_id!r} has not been started")
        return run

    def _require_bound(self) -> tuple[str, str]:
        """Return bound identifiers or fail before touching the database.

        返回已绑定的标识；未绑定时在访问数据库前直接报错。
        """

        if not self.run_id or not self.user_id:
            raise RuntimeError("No active run is bound")
        return self.run_id, self.user_id

    @staticmethod
    def _event_model(run_id: str, event: RunEvent) -> AgentRunEventModel:
        """Convert the API event model into its persistence representation.

        将 API 事件模型转换为对应的持久化模型。
        """

        return AgentRunEventModel(
            run_id=run_id,
            event_type=event.event_type,
            payload=event.payload,
            created_at=event.created_at,
        )

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
