"""HTTP and WebSocket endpoints for Agent execution.

Agent 执行所使用的 HTTP 与 WebSocket 接口。
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from superset_agent_service.agents.schemas import (
    AgentRequest,
    AgentResponse,
    AgentSocketRequest,
    SupersetTokenProxyRequest,
)
from superset_agent_service.agents.service import AgentService
from superset_agent_service.auth.dependencies import get_permission_context
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.auth.superset_token import (
    AgentTokenVerificationError,
    token_verifier,
)
from superset_agent_service.config import settings

router = APIRouter()


@router.post("/dev/superset-token")
async def proxy_superset_agent_token(
    request: SupersetTokenProxyRequest,
) -> dict[str, object]:
    """Proxy a debug-page token request to Superset with a real Cookie header.

    将调试页的 Token 请求代理到 Superset，并使用真正的 Cookie 请求头。

    Browser JavaScript cannot set the standard ``Cookie`` header.  The local
    debug page therefore posts the pasted cookie to this endpoint, and this
    server-side proxy forwards it to Superset.  Keep this endpoint for local
    development only; integrated Superset pages should call Superset directly.

    浏览器 JavaScript 不能设置标准 ``Cookie`` 请求头。因此本地调试页会把手动粘贴的
    Cookie 发到这里，再由服务端代理转发给 Superset。该接口仅用于本地开发；真正集成到
    Superset 的页面应直接调用 Superset 后端接口。
    """

    base_url = request.superset_base_url.strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=400, detail="superset_base_url is required.")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": base_url,
        "Origin": base_url,
    }
    if request.cookie.strip():
        headers["Cookie"] = request.cookie.strip()
        csrf_token = _csrf_from_cookie(request.cookie)
        if csrf_token:
            headers["X-CSRFToken"] = csrf_token

    url = f"{base_url}/api/v1/agent/token"
    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        response = await client.post(url, json={}, headers=headers)
    content_type = response.headers.get("content-type", "")
    body: object
    if "application/json" in content_type:
        body = response.json()
    else:
        body = response.text
    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=body,
        )
    if not isinstance(body, dict):
        raise HTTPException(status_code=502, detail="Superset returned non-JSON token response.")
    return body


@router.post("/chat", response_model=AgentResponse)
async def chat(
    request: AgentRequest,
    context: PermissionContext = Depends(get_permission_context),
) -> AgentResponse:
    """Execute one Agent request through the standard HTTP interface.

    通过标准 HTTP 接口执行一次 Agent 请求。
    """

    service = AgentService()
    return await service.chat(request=request, context=context)


@router.websocket("/ws")
async def agent_socket(websocket: WebSocket) -> None:
    """Run Agents over one persistent connection with live event delivery.

    通过一个持久 WebSocket 连接运行 Agent，并实时发送执行事件。
    """

    await websocket.accept()
    await websocket.send_json({"type": "connected"})

    authenticated_context: PermissionContext | None = None
    query_token = _token_from_query(websocket)
    if settings.SUPERSET_AGENT_TOKEN_VERIFY_URL and query_token:
        try:
            authenticated_context = await token_verifier.verify(query_token)
            await websocket.send_json({"type": "authenticated"})
        except AgentTokenVerificationError as exc:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": str(exc),
                    "code": "agent_token_invalid",
                }
            )

    async def send_event(message: dict[str, object]) -> None:
        """Forward one runtime event to the connected browser.

        将一条运行时事件转发给当前连接的浏览器。
        """

        await websocket.send_json(message)

    try:
        # One WebSocket can process multiple requests until the client disconnects.
        # 同一个 WebSocket 可连续处理多个请求，直到客户端主动断开连接。
        while True:
            raw_message = await websocket.receive_json()

            if raw_message.get("type") == "auth":
                authenticated_context = await _authenticate_socket_message(
                    raw_message=raw_message,
                    websocket=websocket,
                )
                continue

            try:
                socket_request = AgentSocketRequest.model_validate(raw_message)
                context = await _context_for_socket_request(
                    socket_request=socket_request,
                    websocket=websocket,
                    authenticated_context=authenticated_context,
                )
                response = await AgentService(event_sink=send_event).chat(
                    request=socket_request.request,
                    context=context,
                )
                await websocket.send_json(
                    {
                        "type": "final",
                        "response": response.model_dump(mode="json"),
                    }
                )
            except ValidationError as exc:
                # Validation errors are returned without closing the connection.
                # 参数校验失败时只返回错误，不关闭当前连接。
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": "Invalid Agent request",
                        "details": exc.errors(include_url=False),
                    }
                )
            except AgentTokenVerificationError as exc:
                # Authentication failures are scoped to the current message so the
                # browser can refresh its token and retry on the same connection.
                # 认证失败只影响当前消息，浏览器可以刷新 Token 后在同一连接重试。
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": str(exc),
                        "code": "agent_token_invalid",
                    }
                )
            except Exception as exc:
                # Runtime failures are isolated to the current Agent request.
                # 运行时异常只影响本次 Agent 请求，不影响后续请求。
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": str(exc),
                    }
                )
    except WebSocketDisconnect:
        # A browser refresh or tab close normally reaches this branch.
        # 浏览器刷新或关闭标签页时，通常会进入此分支。
        return


async def _authenticate_socket_message(
    raw_message: dict[str, object],
    websocket: WebSocket,
) -> PermissionContext:
    """Verify a standalone WebSocket auth message and acknowledge it.

    校验独立的 WebSocket 认证消息，并返回确认。
    """

    token = _token_from_raw_message(raw_message) or _token_from_query(websocket)
    if not token:
        raise AgentTokenVerificationError("Missing Agent token.")

    context = await token_verifier.verify(token)
    await websocket.send_json({"type": "authenticated"})
    return context


async def _context_for_socket_request(
    socket_request: AgentSocketRequest,
    websocket: WebSocket,
    authenticated_context: PermissionContext | None,
) -> PermissionContext:
    """Resolve the trusted context for one WebSocket run request.

    为一次 WebSocket 运行请求解析可信权限上下文。
    """

    if settings.SUPERSET_AGENT_TOKEN_VERIFY_URL:
        token = socket_request.get_agent_token()
        if token:
            return await token_verifier.verify(token)
        if authenticated_context:
            return authenticated_context
        token = _token_from_query(websocket)
        if token:
            return await token_verifier.verify(token)
        raise AgentTokenVerificationError("Missing Agent token.")

    # Local development fallback only. In production, Superset token verification
    # must be enabled and the browser-provided context is ignored.
    # 仅用于本地开发。生产环境必须开启 Superset Token 校验，并忽略浏览器传入的 context。
    return PermissionContext(
        user_id=socket_request.context.user_id,
        tenant_id=socket_request.context.tenant_id,
        roles=socket_request.context.roles,
    )


def _token_from_raw_message(raw_message: dict[str, object]) -> str | None:
    """Read any supported token field from an arbitrary WebSocket message.

    从任意 WebSocket 消息中读取支持的 Token 字段。
    """

    for key in ("token", "agent_token", "access_token"):
        value = raw_message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _token_from_query(websocket: WebSocket) -> str | None:
    """Support query-token clients while preferring message-body tokens.

    兼容通过查询参数传 Token 的客户端，但更推荐放在消息体中。
    """

    for key in ("token", "agent_token", "access_token"):
        value = websocket.query_params.get(key)
        if value:
            return value
    return None


def _csrf_from_cookie(cookie: str) -> str | None:
    """Extract a likely CSRF token from a raw Cookie header value.

    从原始 Cookie 字符串中提取可能的 CSRF Token。
    """

    for chunk in cookie.split(";"):
        name, _, value = chunk.strip().partition("=")
        if name in {"csrf_token", "csrf_access_token", "X-CSRFToken"} and value:
            return value
    return None
