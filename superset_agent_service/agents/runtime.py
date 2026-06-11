"""Agent Runtime that lets DeepSeek reason over Superset MCP tools.

让 DeepSeek 基于 Superset MCP 工具进行推理的 Agent Runtime。
"""

import asyncio
import json
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from superset_agent_service.agents.llm_client import OpenAICompatibleChatClient
from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.config import settings
from superset_agent_service.runs.service import RunService
from superset_agent_service.tools.mcp_client import MCPClient
from superset_agent_service.tools.registry import ToolRegistry
from superset_agent_service.tools.superset_mcp import get_superset_mcp_client


SYSTEM_PROMPT = """\
You are a Superset analytics assistant.

Use the available MCP tools whenever the user asks about dashboards, charts,
datasets, databases, SQL, reports, users, roles, or data stored in Superset.
Never invent tool results. Follow each tool's JSON schema exactly.

When a list tool supports select_columns, request every field needed to answer
the user. For dashboard publication questions, list_dashboards must request
id, dashboard_title, and published. A missing field means "unknown"; never
interpret a missing boolean field as false.

If search_tools and call_tool are available, use search_tools to discover the
best hidden tool and call_tool to execute it. Give the final answer in the same
language as the user. Summarize useful results clearly and mention errors
honestly.
"""


class AgentGraphState(TypedDict):
    """Mutable state passed between the LangGraph nodes.

    在 LangGraph 节点之间传递的可变状态。

    ``messages`` is the complete OpenAI-compatible conversation.  The model
    node appends assistant messages, while the tool node appends MCP results.
    Keeping those writes in separate nodes makes the reasoning cycle visible
    in both code and future graph visualizations.

    ``messages`` 保存完整的 OpenAI 兼容对话。模型节点追加 assistant 消息，
    工具节点追加 MCP 结果。把两类写入放在不同节点中，可以让推理循环在代码和
    后续图形化展示中都更加清晰。
    """

    messages: list[dict[str, Any]]
    model_tools: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]
    step: int
    answer: str | None


class LangGraphRuntime:
    """Coordinate DeepSeek reasoning and MCP execution with a LangGraph graph.

    使用 LangGraph 图协调 DeepSeek 推理与 MCP 工具执行。
    """

    def __init__(
        self,
        tools: ToolRegistry,
        runs: RunService,
        llm: OpenAICompatibleChatClient | None = None,
        mcp: MCPClient | None = None,
    ):
        """Create the model, MCP, and graph dependencies used by each run.

        创建每次运行所需的模型、MCP 和图依赖。
        """

        self.tools = tools
        self.runs = runs
        self.llm = llm or OpenAICompatibleChatClient(
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            timeout_seconds=settings.MAX_RUN_SECONDS,
        )
        self.mcp = mcp or get_superset_mcp_client()
        self.graph = self._build_graph()

    async def invoke(self, request: AgentRequest, context: PermissionContext) -> str:
        """Execute one bounded Agent run and return its final text answer.

        执行一次有时间限制的 Agent 运行，并返回最终文本答案。
        """

        await self.runs.record_event(
            event_type="plan",
            payload={
                "question": request.question,
                "dashboard_id": request.dashboard_id,
                "chart_id": request.chart_id,
            },
        )

        if self.mcp is None:
            raise RuntimeError(
                "SUPERSET_MCP_URL is not configured; Runtime cannot discover tools"
            )

        # The outer timeout covers the complete reasoning run, including every
        # model request and MCP call.  Individual HTTP clients also have their
        # own timeout, but this prevents a long sequence from exceeding the
        # service-level budget.
        # 外层超时覆盖完整推理过程，包括所有模型请求和 MCP 调用。各 HTTP 客户端
        # 虽然也有自己的超时，但这里可防止多轮调用超过服务级时间预算。
        try:
            return await asyncio.wait_for(
                self._run_tool_loop(request=request, context=context),
                timeout=settings.MAX_RUN_SECONDS,
            )
        except TimeoutError as exc:
            raise RuntimeError(
                f"Agent run exceeded {settings.MAX_RUN_SECONDS} seconds"
            ) from exc

    async def _run_tool_loop(
        self,
        request: AgentRequest,
        context: PermissionContext,
    ) -> str:
        """Discover tools, initialize graph state, and run the reasoning loop.

        发现可用工具、初始化图状态并执行推理循环。
        """

        mcp_tools = await self.mcp.list_tools()
        model_tools = self._to_model_tools(mcp_tools)

        await self.runs.record_event(
            event_type="tools_discovered",
            payload={
                "count": len(model_tools),
                "names": [
                    tool["function"]["name"]
                    for tool in model_tools
                    if isinstance(tool.get("function"), dict)
                ],
            },
        )

        initial_state: AgentGraphState = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": self._build_user_message(request, context),
                },
            ],
            "model_tools": model_tools,
            "pending_tool_calls": [],
            "step": 0,
            "answer": None,
        }

        final_state = await self.graph.ainvoke(
            initial_state,
            # Each reasoning round visits model -> tools.  The small buffer also
            # allows the final model -> END transition without hitting the
            # framework's recursion guard.
            # 每轮推理都会经过 model -> tools；额外缓冲允许最后一次 model -> END
            # 转换完成，而不会触发框架的递归保护限制。
            config={"recursion_limit": settings.MAX_AGENT_STEPS * 2 + 2},
        )
        answer = final_state.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("LangGraph completed without a final answer")
        return answer.strip()

    def _build_graph(self):
        """Compile the two-node reasoning graph used for every Agent run.

        编译每次 Agent 运行都会使用的双节点推理图。

        Graph shape:

            START -> model -> tools -> model -> ... -> END

        The conditional edge after ``model`` ends the run when DeepSeek returns
        normal content, or routes to ``tools`` when it requests MCP calls.

        ``model`` 后的条件边会在 DeepSeek 返回普通内容时结束运行；当模型请求
        MCP 工具时，则把流程转到 ``tools`` 节点。
        """

        builder = StateGraph(AgentGraphState)
        builder.add_node("model", self._model_node)
        builder.add_node("tools", self._tools_node)
        builder.add_edge(START, "model")
        builder.add_conditional_edges(
            "model",
            self._route_after_model,
            {"tools": "tools", "end": END},
        )
        builder.add_edge("tools", "model")
        return builder.compile()

    async def _model_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Ask DeepSeek for either a final answer or the next MCP tool calls.

        请求 DeepSeek 返回最终答案，或给出下一批 MCP 工具调用。
        """

        step = state["step"] + 1
        if step > settings.MAX_AGENT_STEPS:
            raise RuntimeError(
                f"Agent reached MAX_AGENT_STEPS={settings.MAX_AGENT_STEPS} "
                "without producing a final answer"
            )

        assistant_message = await self.llm.complete(
            state["messages"],
            state["model_tools"],
            on_content_delta=self._publish_answer_delta,
        )
        messages = [*state["messages"], assistant_message]
        raw_tool_calls = assistant_message.get("tool_calls", [])
        tool_calls = raw_tool_calls if isinstance(raw_tool_calls, list) else []

        if tool_calls:
            await self.runs.record_event(
                event_type="tool_plan",
                payload={
                    "step": step,
                    "tools": [
                        call.get("function", {}).get("name")
                        for call in tool_calls
                        if isinstance(call, dict)
                    ],
                },
            )
            return {
                "messages": messages,
                "pending_tool_calls": tool_calls,
                "step": step,
                "answer": None,
            }

        content = assistant_message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Model returned neither an answer nor a tool call")

        await self.runs.record_event(
            event_type="answer_generated",
            payload={"step": step},
        )
        return {
            "messages": messages,
            "pending_tool_calls": [],
            "step": step,
            "answer": content.strip(),
        }

    async def _tools_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Execute every MCP call requested in the preceding model node.

        执行上一个模型节点请求的全部 MCP 调用。
        """

        tool_messages: list[dict[str, Any]] = []
        # DeepSeek may request several independent tools in one response.
        # Sequential execution keeps traces deterministic and leaves a clear
        # insertion point for per-tool permission checks.
        # DeepSeek 一次可能请求多个相互独立的工具。顺序执行可保持轨迹确定性，
        # 也为后续加入逐工具权限检查预留了清晰位置。
        for tool_call in state["pending_tool_calls"]:
            tool_messages.append(await self._execute_tool_call(tool_call))

        return {
            "messages": [*state["messages"], *tool_messages],
            "pending_tool_calls": [],
        }

    @staticmethod
    def _route_after_model(state: AgentGraphState) -> Literal["tools", "end"]:
        """Choose the graph's next edge from the latest model decision.

        根据模型最新决策选择图中的下一条边。
        """

        return "tools" if state["pending_tool_calls"] else "end"

    async def _publish_answer_delta(self, delta: str) -> None:
        """Forward one genuine model token chunk to connected WebSocket clients.

        将模型真实产生的一段 Token 转发给已连接的 WebSocket 客户端。
        """

        await self.runs.publish_transient(
            event_type="answer_delta",
            payload={"delta": delta},
        )

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Validate one model tool request, call MCP, and build a tool message.

        校验一次模型工具请求、调用 MCP，并构造 tool 消息。
        """

        call_id = str(tool_call.get("id", ""))
        function = tool_call.get("function")
        if not call_id or not isinstance(function, dict):
            raise RuntimeError("Model returned an invalid tool call")

        name = function.get("name")
        raw_arguments = function.get("arguments", "{}")
        if not isinstance(name, str) or not name:
            raise RuntimeError("Model tool call is missing a function name")

        try:
            arguments = (
                json.loads(raw_arguments)
                if isinstance(raw_arguments, str)
                else raw_arguments
            )
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Model generated invalid JSON arguments for {name}: {exc}"
            ) from exc
        if not isinstance(arguments, dict):
            raise RuntimeError(f"Tool arguments for {name} must be a JSON object")

        await self.runs.record_event(
            event_type="tool_started",
            payload={"tool": name, "arguments": arguments},
        )

        try:
            result = await self.mcp.call_tool(name, arguments)
            content = json.dumps(result, ensure_ascii=False, default=str)
            await self.runs.record_event(
                event_type="tool_completed",
                payload={"tool": name},
            )
        except Exception as exc:
            # Returning a failed tool message gives the model a chance to
            # recover, choose another tool, or explain the failure to the user.
            # 将失败信息作为 tool 消息返回，可让模型尝试恢复、改用其他工具，
            # 或向用户解释失败原因。
            content = json.dumps(
                {"error": str(exc), "tool": name},
                ensure_ascii=False,
            )
            await self.runs.record_event(
                event_type="tool_failed",
                payload={"tool": name, "error": str(exc)},
            )

        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": content,
        }

    @staticmethod
    def _to_model_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert MCP tool definitions to OpenAI/DeepSeek function tools.

        将 MCP 工具定义转换为 OpenAI/DeepSeek 的函数工具格式。
        """

        converted: list[dict[str, Any]] = []
        for tool in mcp_tools:
            name = tool.get("name")
            if not isinstance(name, str) or not name:
                continue
            schema = tool.get("inputSchema", {"type": "object", "properties": {}})
            if not isinstance(schema, dict):
                schema = {"type": "object", "properties": {}}
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": str(tool.get("description", "")),
                        "parameters": schema,
                    },
                }
            )
        return converted

    @staticmethod
    def _build_user_message(
        request: AgentRequest,
        context: PermissionContext,
    ) -> str:
        """Combine the question with optional UI context without changing it.

        在不改写用户问题的前提下，附加可选的界面上下文。
        """

        supplemental = {
            "dashboard_id": request.dashboard_id,
            "chart_id": request.chart_id,
            "filters": request.filters,
            "time_range": request.time_range,
            "request_user_id": context.user_id,
        }
        return (
            f"User question:\n{request.question}\n\n"
            "Optional request context (null values can be ignored):\n"
            f"{json.dumps(supplemental, ensure_ascii=False, default=str)}"
        )
