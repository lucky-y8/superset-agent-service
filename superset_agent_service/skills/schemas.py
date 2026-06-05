"""Schemas that describe high-level agent skills."""

from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    name: str
    description: str
    intent_examples: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    risk_level: str = "low"


class SkillMatch(BaseModel):
    skill_name: str
    confidence: float
    reason: str | None = None

