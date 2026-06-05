"""Lightweight skill router placeholder for future intent classification."""

from superset_agent_service.skills.schemas import SkillMatch


class SkillRouter:
    async def route(self, question: str) -> SkillMatch:
        normalized = question.lower()
        if "sql" in normalized or "查询" in question:
            return SkillMatch(skill_name="text_to_sql", confidence=0.6)
        if "为什么" in question or "异常" in question:
            return SkillMatch(skill_name="metric_investigator", confidence=0.6)
        return SkillMatch(skill_name="dashboard_explainer", confidence=0.5)

