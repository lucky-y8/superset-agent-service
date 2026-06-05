"""Schemas for administrative runtime configuration APIs."""

from pydantic import BaseModel


class RuntimeConfig(BaseModel):
    default_model_provider: str
    default_model_name: str
    max_agent_steps: int
    max_run_seconds: int
