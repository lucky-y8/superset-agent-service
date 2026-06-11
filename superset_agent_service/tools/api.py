"""Development endpoints for inspecting and calling the configured MCP server.

用于查看和调用已配置 MCP 服务的开发调试接口。
"""

from fastapi import APIRouter, HTTPException

from superset_agent_service.config import settings
from superset_agent_service.tools.mcp_client import MCPError, MCPTransportError
from superset_agent_service.tools.schemas import (
    MCPServerInfo,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolListResponse,
    MCPToolSummary,
)
from superset_agent_service.tools.superset_mcp import get_superset_mcp_client

router = APIRouter()


def _require_client():
    """Return the configured client or a clear configuration error.

    返回已配置客户端；配置缺失时给出明确错误。

    This helper keeps the same behavior across all MCP endpoints and avoids
    duplicating a fragile ``None`` check in every route.

    此辅助函数让所有 MCP 接口行为保持一致，也避免在每个路由中重复容易遗漏的
    ``None`` 检查。
    """

    if settings.ENVIRONMENT.lower() not in {"local", "development", "test"}:
        # The raw call endpoint intentionally bypasses the future Agent policy
        # workflow, so exposing it in production would create a security hole.
        # 原始调用接口会绕过未来的 Agent 策略流程，因此若在生产环境暴露，
        # 会形成安全风险。
        raise HTTPException(
            status_code=404,
            detail="MCP development API is disabled in this environment",
        )

    client = get_superset_mcp_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="SUPERSET_MCP_URL is not configured",
        )
    return client


def _gateway_error(exc: Exception) -> HTTPException:
    """Convert low-level transport/protocol failures into a stable API error.

    将底层传输或协议异常转换为稳定的 API 错误。
    """

    detail = str(exc)
    return HTTPException(status_code=502, detail=detail)


@router.get("/status", response_model=MCPServerInfo)
async def get_mcp_status() -> MCPServerInfo:
    """Perform an MCP handshake and report the visible tool count.

    执行 MCP 握手，并报告当前可见的工具数量。
    """

    client = _require_client()
    try:
        initialization = await client.initialize()
        tools = await client.list_tools()
    except (MCPTransportError, MCPError) as exc:
        raise _gateway_error(exc) from exc

    server_info = initialization.get("serverInfo", {})
    if not isinstance(server_info, dict):
        server_info = {}

    return MCPServerInfo(
        connected=True,
        endpoint=client.base_url,
        protocol_version=initialization.get("protocolVersion"),
        server_name=server_info.get("name"),
        server_version=server_info.get("version"),
        tool_count=len(tools),
        message=(
            "MCP server is online"
            if tools
            else "MCP server is online, but the current identity sees no tools"
        ),
    )


@router.get("/tools", response_model=MCPToolListResponse)
async def list_mcp_tools() -> MCPToolListResponse:
    """List tools after normalizing the server's JSON Schema field names.

    规范化服务端 JSON Schema 字段名后返回工具列表。
    """

    client = _require_client()
    try:
        tools = await client.list_tools()
    except (MCPTransportError, MCPError) as exc:
        raise _gateway_error(exc) from exc

    summaries = [
        MCPToolSummary(
            name=str(tool.get("name", "")),
            description=str(tool.get("description", "")),
            # MCP names this field ``inputSchema``.  Keeping the conversion at
            # the HTTP boundary gives our frontend a Python-style field name.
            # MCP 将该字段命名为 ``inputSchema``。在 HTTP 边界完成转换后，
            # 前端即可使用符合 Python 风格的字段名。
            input_schema=tool.get("inputSchema", {}),
        )
        for tool in tools
        if isinstance(tool, dict) and tool.get("name")
    ]
    return MCPToolListResponse(endpoint=client.base_url, tools=summaries)


@router.post("/call", response_model=MCPToolCallResponse)
async def call_mcp_tool(request: MCPToolCallRequest) -> MCPToolCallResponse:
    """Call one visible MCP tool for development-time protocol verification.

    调用一个可见的 MCP 工具，用于开发阶段的协议验证。
    """

    client = _require_client()
    try:
        result = await client.call_tool(request.name, request.arguments)
    except (MCPTransportError, MCPError) as exc:
        raise _gateway_error(exc) from exc
    return MCPToolCallResponse(name=request.name, result=result)
