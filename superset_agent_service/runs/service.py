"""In-memory run trace service used until database persistence is added."""

from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.runs.schemas import RunEvent, RunTrace


class RunService:
    _store: dict[str, RunTrace] = {}

    def __init__(self) -> None:
        self.run_id: str | None = None
        self.user_id: str | None = None

    def bind_run(self, run_id: str, user_id: str) -> None:
        self.run_id = run_id
        self.user_id = user_id
        self._store[run_id] = RunTrace(run_id=run_id, user_id=user_id, status="created")

    async def start_run(
        self, request: AgentRequest, context: PermissionContext
    ) -> None:
        await self.record_event(
            event_type="run_started",
            payload={"user_id": context.user_id, "question": request.question},
        )

    async def complete_run(self, status: str = "completed") -> None:
        self._current().status = status
        await self.record_event(event_type="run_completed")

    async def fail_run(self, error: str) -> None:
        self._current().status = "failed"
        await self.record_event(event_type="run_failed", payload={"error": error})

    async def record_event(
        self, event_type: str, payload: dict[str, object] | None = None
    ) -> None:
        self._current().events.append(
            RunEvent(event_type=event_type, payload=payload or {})
        )

    @classmethod
    def get_trace(cls, run_id: str) -> RunTrace | None:
        return cls._store.get(run_id)

    def _current(self) -> RunTrace:
        if not self.run_id or self.run_id not in self._store:
            raise RuntimeError("No active run is bound")
        return self._store[self.run_id]
