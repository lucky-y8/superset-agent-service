"""FastAPI dependencies that build the current permission context.

用于构建当前权限上下文的 FastAPI 依赖。
"""

from fastapi import Header

from superset_agent_service.auth.schemas import PermissionContext


async def get_permission_context(
    x_user_id: str = Header(default="local-user"),
    x_tenant_id: str | None = Header(default=None),
    x_roles: str = Header(default="admin"),
) -> PermissionContext:
    """Convert trusted request headers into a normalized permission context.

    将可信请求头转换为规范化的权限上下文。
    """

    roles = [role.strip() for role in x_roles.split(",") if role.strip()]
    return PermissionContext(user_id=x_user_id, tenant_id=x_tenant_id, roles=roles)
