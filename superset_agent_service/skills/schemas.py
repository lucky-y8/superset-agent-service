"""Schemas that describe high-level agent skills.

描述 Agent 高层业务技能的数据模型。
"""

from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    """Define one reusable business capability and its tool dependencies.

    定义一个可复用的业务能力及其工具依赖。
    """

    name: str
    description: str
    intent_examples: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    risk_level: str = "low"


class SkillMatch(BaseModel):
    """Represent the router's best skill candidate for a user question.

    表示路由器为用户问题选出的最佳技能候选项。
    """

    skill_name: str
    confidence: float
    reason: str | None = None
