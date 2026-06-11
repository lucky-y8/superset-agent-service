"""Request and response schemas for Agent APIs.

Agent 接口使用的请求与响应数据模型。
"""

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    """Describe the user's question and optional Superset page context.

    描述用户问题以及可选的 Superset 页面上下文。
    """

    question: str
    dashboard_id: str | None = None
    chart_id: str | None = None
    filters: dict[str, object] = Field(default_factory=dict)
    time_range: str | None = None


class AgentResponse(BaseModel):
    """Return the final answer and the identifier of its execution trace.

    返回最终答案及其执行轨迹标识。
    """

    run_id: str
    answer: str
    status: str


class AgentSocketContext(BaseModel):
    """Permission context sent in a browser WebSocket message.

    浏览器通过 WebSocket 消息发送的权限上下文。
    """

    user_id: str = "local-user"
    tenant_id: str | None = "local"
    roles: list[str] = Field(default_factory=lambda: ["admin"])


class AgentSocketRequest(BaseModel):
    """One Agent run requested over the persistent WebSocket connection.

    通过持久 WebSocket 连接发起的一次 Agent 运行请求。
    """

    type: str = "run"
    request: AgentRequest
    context: AgentSocketContext = Field(default_factory=AgentSocketContext)
