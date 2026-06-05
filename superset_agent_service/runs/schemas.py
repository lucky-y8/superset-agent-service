"""Schemas that describe run lifecycle traces and their events."""

from datetime import datetime
from pydantic import BaseModel, Field


class RunEvent(BaseModel):
    event_type: str
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RunTrace(BaseModel):
    run_id: str
    user_id: str
    status: str
    events: list[RunEvent] = Field(default_factory=list)
