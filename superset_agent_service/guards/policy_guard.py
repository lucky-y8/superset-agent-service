"""Policy guardrail boundary for checking tool-level permissions.

用于检查工具级权限的策略护栏边界。
"""

from superset_agent_service.auth.schemas import PermissionContext


class PolicyGuard:
    """Apply the simplest tool allow-list policy for the current identity.

    为当前身份应用基础的工具白名单策略。
    """

    def can_use_tool(self, context: PermissionContext, tool_name: str) -> bool:
        """Decide whether the identity may execute the named tool.

        判断当前身份是否可以执行指定工具。
        """

        if context.is_admin:
            return True
        return tool_name in context.allowed_tools
