"""Registry for selecting business skills before tool execution."""

from superset_agent_service.skills.schemas import SkillDefinition


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    @classmethod
    def default(cls) -> "SkillRegistry":
        registry = cls()
        registry.register(
            SkillDefinition(
                name="dashboard_explainer",
                description="Explain the current Superset dashboard or chart.",
                intent_examples=["解释这个 dashboard", "这个图表说明了什么"],
                required_tools=["superset_mcp"],
                risk_level="low",
            )
        )
        registry.register(
            SkillDefinition(
                name="metric_investigator",
                description="Investigate why a metric increased, decreased, or changed.",
                intent_examples=["为什么指标上涨", "分析这个异常波动"],
                required_tools=["superset_mcp", "rag_retriever", "sql_guard"],
                risk_level="medium",
            )
        )
        registry.register(
            SkillDefinition(
                name="text_to_sql",
                description="Translate natural language questions into guarded SQL.",
                intent_examples=["帮我写 SQL", "查询本周成本"],
                required_tools=["sql_guard", "superset_mcp"],
                risk_level="high",
            )
        )
        return registry

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition:
        return self._skills[name]

    def list_skills(self) -> list[SkillDefinition]:
        return list(self._skills.values())

