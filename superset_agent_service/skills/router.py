"""Lightweight skill router placeholder for future intent classification.

为后续意图分类预留的轻量级技能路由器。
"""

from superset_agent_service.skills.schemas import SkillMatch


class SkillRouter:
    """Select a candidate business skill using simple keyword rules.

    使用简单关键词规则选择候选业务技能。
    """

    async def route(self, question: str) -> SkillMatch:
        """Return the most likely skill and a provisional confidence score.

        返回最可能的技能及其临时置信度。
        """

        normalized = question.lower()
        if "sql" in normalized or "查询" in question:
            return SkillMatch(skill_name="text_to_sql", confidence=0.6)
        if "为什么" in question or "异常" in question:
            return SkillMatch(skill_name="metric_investigator", confidence=0.6)
        return SkillMatch(skill_name="dashboard_explainer", confidence=0.5)
