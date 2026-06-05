"""Request and response schemas for Agent APIs."""

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    question: str
    dashboard_id: str | None = None
    chart_id: str | None = None
    filters: dict[str, object] = Field(default_factory=dict)
    time_range: str | None = None


class AgentResponse(BaseModel):
    run_id: str
    answer: str
    status: str
