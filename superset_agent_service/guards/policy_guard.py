"""Policy guardrail boundary for checking tool-level permissions."""

from superset_agent_service.auth.schemas import PermissionContext


class PolicyGuard:
    def can_use_tool(self, context: PermissionContext, tool_name: str) -> bool:
        if context.is_admin:
            return True
        return tool_name in context.allowed_tools
