"""FastAPI dependencies that build the current permission context.

用于构建当前权限上下文的 FastAPI 依赖。
"""

from fastapi import Header, HTTPException, status

from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.auth.superset_token import (
    AgentTokenVerificationError,
    token_error_to_http,
    token_verifier,
)
from superset_agent_service.config import settings


async def get_permission_context(
    authorization: str | None = Header(default=None),
    x_user_id: str = Header(default="local-user"),
    x_tenant_id: str | None = Header(default=None),
    x_roles: str = Header(default="admin"),
) -> PermissionContext:
    """Build a trusted permission context for one HTTP Agent request.

    为一次 HTTP Agent 请求构建可信权限上下文。
    """

    if settings.SUPERSET_AGENT_TOKEN_VERIFY_URL:
        token = _bearer_token(authorization)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Agent bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return await token_verifier.verify(token)
        except AgentTokenVerificationError as exc:
            raise token_error_to_http(exc) from exc

    # Local development fallback: these headers are convenient for direct API
    # tests, but production must configure SUPERSET_AGENT_TOKEN_VERIFY_URL.
    # 本地开发兜底：这些请求头便于直接测试 API；生产环境必须配置
    # SUPERSET_AGENT_TOKEN_VERIFY_URL，不能信任前端传来的身份。
    roles = [role.strip() for role in x_roles.split(",") if role.strip()]
    return PermissionContext(user_id=x_user_id, tenant_id=x_tenant_id, roles=roles)


def _bearer_token(authorization: str | None) -> str | None:
    """Extract a bearer token from the Authorization header.

    从 Authorization 请求头中提取 Bearer Token。
    """

    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()
