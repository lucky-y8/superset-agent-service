"""Superset-issued Agent token verification.

Superset 签发的 Agent Token 校验逻辑。
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, status

from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.config import settings

logger = logging.getLogger(__name__)


class AgentTokenVerificationError(Exception):
    """Raised when Superset rejects or cannot verify an Agent token.

    当 Superset 拒绝 Token，或 Agent Service 无法完成校验时抛出。
    """


@dataclass
class _CachedContext:
    """Store one verified context until its short cache deadline.

    保存一个已校验的用户上下文，直到短缓存过期。
    """

    context: PermissionContext
    expires_at: float


class SupersetAgentTokenVerifier:
    """Verify browser-provided Agent tokens against Superset.

    通过 Superset 后端校验浏览器传来的 Agent Token。
    """

    def __init__(self) -> None:
        """Create an in-process cache for successful verification results.

        创建一个进程内短缓存，用于保存校验成功的结果。
        """

        self._cache: dict[str, _CachedContext] = {}

    async def verify(self, token: str) -> PermissionContext:
        """Return a trusted permission context for a Superset Agent token.

        根据 Superset Agent Token 返回可信的权限上下文。
        """

        if not settings.SUPERSET_AGENT_TOKEN_VERIFY_URL:
            raise AgentTokenVerificationError(
                "Superset token verification URL is not configured."
            )

        cache_key = self._hash_token(token)
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached and cached.expires_at > now:
            context = cached.context.model_copy(
                update={"mcp_bearer_token": token},
            )
            logger.info(
                "Agent token verify cache hit: user_id=%s username=%s tools=%s",
                context.user_id,
                context.username,
                context.allowed_tools,
            )
            return context

        payload = await self._call_superset(token)
        context = self._context_from_payload(payload)
        logger.info(
            "Agent token verified by Superset: user_id=%s username=%s tools=%s datasets=%s",
            context.user_id,
            context.username,
            context.allowed_tools,
            context.allowed_dataset_ids,
        )

        ttl = max(0, min(settings.AGENT_TOKEN_VERIFY_CACHE_SECONDS, 60))
        if ttl:
            self._cache[cache_key] = _CachedContext(
                context=context,
                expires_at=now + ttl,
            )
        return context.model_copy(update={"mcp_bearer_token": token})

    async def _call_superset(self, token: str) -> dict[str, Any]:
        """Call Superset's internal verification endpoint.

        调用 Superset 内部 Token 校验接口。
        """

        headers: dict[str, str] = {}
        if settings.SUPERSET_AGENT_SERVICE_KEY:
            headers["X-Agent-Service-Key"] = settings.SUPERSET_AGENT_SERVICE_KEY

        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                logger.info(
                    "Verifying Agent token with Superset: url=%s token_sha256=%s",
                    settings.SUPERSET_AGENT_TOKEN_VERIFY_URL,
                    cache_safe_token_hash(token),
                )
                response = await client.post(
                    settings.SUPERSET_AGENT_TOKEN_VERIFY_URL,
                    json={"token": token},
                    headers=headers,
                )

        except httpx.HTTPError as exc:
            logger.exception(
                "Superset token verification request failed before response: url=%s",
                settings.SUPERSET_AGENT_TOKEN_VERIFY_URL,
            )
            raise AgentTokenVerificationError(
                "Superset token verification request failed."
            ) from exc

        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            raise AgentTokenVerificationError("Invalid or expired Agent token.")

        if response.status_code >= 400:
            logger.warning(
                "Superset token verification rejected: status=%s body=%s",
                response.status_code,
                response.text[:1200],
            )
            raise AgentTokenVerificationError(
                f"Superset token verification failed: {response.status_code}.{response.text}"
            )

        data = response.json()
        result = data.get("result", data)
        if not isinstance(result, dict):
            raise AgentTokenVerificationError("Invalid verification response.")
        logger.info(
            "Superset token verify response: status=%s keys=%s result_keys=%s",
            response.status_code,
            sorted(data.keys()),
            sorted(result.keys()),
        )
        return result

    def _context_from_payload(self, payload: dict[str, Any]) -> PermissionContext:
        """Convert Superset verification payload into Runtime permissions.

        将 Superset 校验结果转换为 Runtime 使用的权限上下文。
        """

        user_id = payload.get("user_id") or payload.get("sub")
        if user_id is None:
            raise AgentTokenVerificationError("Verification response has no user.")

        permissions = payload.get("permissions") or {}
        scopes = permissions.get("scopes") if isinstance(permissions, dict) else None
        roles = payload.get("roles")
        if roles is None and isinstance(permissions, dict):
            roles = permissions.get("roles")
        dataset_ids = (
            permissions.get("dataset_ids") if isinstance(permissions, dict) else None
        )

        return PermissionContext(
            user_id=str(user_id),
            username=self._optional_string(payload.get("username")),
            tenant_id=self._optional_string(payload.get("tenant_id")),
            # Role names are intentionally not trusted from the browser. Superset
            # should return tool scopes instead; current Superset code may return
            # only the user, so we grant a minimal authenticated marker role.
            # 这里刻意不信任浏览器角色名。生产环境应由 Superset 返回工具 scopes；
            # 当前 Superset 代码可能只返回用户，因此仅给一个“已认证”标记角色。
            roles=self._roles_from_payload(roles),
            allowed_tools=self._tools_from_scopes(scopes),
            allowed_dataset_ids=[
                str(dataset_id) for dataset_id in dataset_ids or []
            ],
        )

    def _tools_from_scopes(self, scopes: Any) -> list[str]:
        """Translate Superset scopes into Agent tool allow-list entries.

        将 Superset scopes 转换为 Agent 工具白名单。
        """

        if not isinstance(scopes, list):
            return []
        tools: list[str] = []
        for scope in scopes:
            if not isinstance(scope, str):
                continue
            if scope == "tool:*":
                tools.append("*")
            elif scope.startswith("tool:"):
                tools.append(scope.removeprefix("tool:"))
        return tools

    def _roles_from_payload(self, roles: Any) -> list[str]:
        """Read trusted Superset role names from the verification response.

        从 Superset 校验响应中读取可信角色名。
        """

        if not isinstance(roles, list):
            return ["authenticated"]
        parsed = [role.strip() for role in roles if isinstance(role, str) and role.strip()]
        return parsed or ["authenticated"]

    def _optional_string(self, value: Any) -> str | None:
        """Convert optional values to strings without turning None into 'None'.

        将可选值转成字符串，同时避免把 None 变成字符串 "None"。
        """

        if value is None:
            return None
        return str(value)

    def _hash_token(self, token: str) -> str:
        """Hash tokens before using them as cache keys.

        对 Token 做哈希后再作为缓存键，避免在内存结构里直接保存完整 Token。
        """

        return hashlib.sha256(token.encode("utf-8")).hexdigest()


token_verifier = SupersetAgentTokenVerifier()


def cache_safe_token_hash(token: str) -> str:
    """Return a short irreversible token fingerprint for logs.

    返回用于日志的短 Token 指纹，不能反推出原始 Token。
    """

    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def token_error_to_http(exc: AgentTokenVerificationError) -> HTTPException:
    """Convert verification failures into a consistent HTTP 401 response.

    将 Token 校验失败转换为统一的 HTTP 401 响应。
    """

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=str(exc),
        headers={"WWW-Authenticate": "Bearer"},
    )
