"""FastAPI dependencies that build the current permission context."""

from fastapi import Header

from superset_agent_service.auth.schemas import PermissionContext


async def get_permission_context(
    x_user_id: str = Header(default="local-user"),
    x_tenant_id: str | None = Header(default=None),
    x_roles: str = Header(default="admin"),
) -> PermissionContext:
    roles = [role.strip() for role in x_roles.split(",") if role.strip()]
    return PermissionContext(user_id=x_user_id, tenant_id=x_tenant_id, roles=roles)
