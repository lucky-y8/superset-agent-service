"""HTTP and WebSocket endpoints for Agent execution.

Agent 执行所使用的 HTTP 与 WebSocket 接口。
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from superset_agent_service.agents.schemas import (
    AgentRequest,
    AgentResponse,
    AgentSocketRequest,
)
from superset_agent_service.agents.service import AgentService
from superset_agent_service.auth.dependencies import get_permission_context
from superset_agent_service.auth.schemas import PermissionContext

router = APIRouter()


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

    通过一个持久连接运行 Agent，并实时发送执行事件。
    """

    await websocket.accept()
    await websocket.send_json({"type": "connected"})

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
            try:
                socket_request = AgentSocketRequest.model_validate(raw_message)
                context = PermissionContext(
                    user_id=socket_request.context.user_id,
                    tenant_id=socket_request.context.tenant_id,
                    roles=socket_request.context.roles,
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
