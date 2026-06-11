"""Pydantic models used by the MCP development API.

MCP 开发调试接口使用的 Pydantic 数据模型。
"""

from typing import Any

from pydantic import BaseModel, Field


class MCPServerInfo(BaseModel):
    """Connection state and negotiated metadata returned by ``initialize``.

    ``initialize`` 返回的连接状态和协商元数据。
    """

    connected: bool
    endpoint: str | None
    protocol_version: str | None = None
    server_name: str | None = None
    server_version: str | None = None
    tool_count: int = 0
    message: str


class MCPToolSummary(BaseModel):
    """The fields a developer needs when selecting and calling an MCP tool.

    开发者选择和调用 MCP 工具时所需的字段。
    """

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class MCPToolListResponse(BaseModel):
    """Return the MCP endpoint and all tools visible to the current identity.

    返回 MCP 端点和当前身份可见的全部工具。
    """

    endpoint: str
    tools: list[MCPToolSummary] = Field(default_factory=list)


class MCPToolCallRequest(BaseModel):
    """Raw debug call request.

    原始调试调用请求。

    ``arguments`` intentionally remains a dictionary because each MCP tool
    publishes a different JSON Schema.  The debug page shows that schema and
    lets the developer provide matching JSON.

    ``arguments`` 特意保留为字典，因为每个 MCP 工具都发布不同的 JSON Schema。
    调试页面会展示该 Schema，并让开发者填写匹配的 JSON。
    """

    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class MCPToolCallResponse(BaseModel):
    """Return the name and unmodified JSON-compatible tool result.

    返回工具名称和未经改写的 JSON 兼容结果。
    """

    name: str
    # JSON-RPC permits any JSON value as a result.  Superset tools commonly
    # return objects, but list tools may legitimately return an array.
    # JSON-RPC 允许结果是任意 JSON 值。Superset 工具通常返回对象，
    # 但列表类工具也可能合法地返回数组。
    result: Any
