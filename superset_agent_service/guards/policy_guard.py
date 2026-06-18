"""Policy guardrail boundary for checking tool-level permissions.

用于检查工具级权限的策略护栏边界。
"""

import logging

from superset_agent_service.auth.schemas import PermissionContext

logger = logging.getLogger(__name__)


class PolicyGuard:
    """Apply the tool allow-list policy for the current identity.

    为当前身份应用工具白名单策略。
    """

    def can_use_tool(self, context: PermissionContext, tool_name: str) -> bool:
        """Decide whether the identity may execute the named tool.

        判断当前身份是否可以执行指定工具。
        """

        if context.is_admin:
            logger.info(
                "PolicyGuard allowed tool by admin role: user_id=%s username=%s tool=%s roles=%s",
                context.user_id,
                context.username,
                tool_name,
                context.roles,
            )
            return True

        allowed_tools = {tool.strip().lower() for tool in context.allowed_tools}
        allowed = "*" in allowed_tools or tool_name.lower() in allowed_tools
        if allowed:
            logger.info(
                "PolicyGuard allowed tool by scope: user_id=%s username=%s tool=%s allowed_tools=%s",
                context.user_id,
                context.username,
                tool_name,
                context.allowed_tools,
            )
        else:
            logger.warning(
                "PolicyGuard denied tool: user_id=%s username=%s tool=%s roles=%s allowed_tools=%s",
                context.user_id,
                context.username,
                tool_name,
                context.roles,
                context.allowed_tools,
            )
        return allowed
