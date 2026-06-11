"""Registry for selecting business skills before tool execution.

在执行工具之前用于选择业务技能的注册表。
"""

from superset_agent_service.skills.schemas import SkillDefinition


class SkillRegistry:
    """Store the business-oriented capabilities known by the Agent.

    保存 Agent 已知的业务能力定义。
    """

    def __init__(self) -> None:
        """Create an empty skill registry.

        创建一个空的技能注册表。
        """

        self._skills: dict[str, SkillDefinition] = {}

    @classmethod
    def default(cls) -> "SkillRegistry":
        """Build the initial set of analytics skills shipped with the service.

        构建服务默认提供的分析类技能集合。
        """

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
        """Register or replace one skill by name.

        按名称注册或替换一个技能。
        """

        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition:
        """Return one registered skill by its exact name.

        按精确名称返回一个已注册技能。
        """

        return self._skills[name]

    def list_skills(self) -> list[SkillDefinition]:
        """Return all currently registered skills.

        返回当前注册的全部技能。
        """

        return list(self._skills.values())
