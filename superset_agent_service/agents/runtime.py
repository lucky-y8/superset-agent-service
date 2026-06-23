"""Agent Runtime that lets DeepSeek reason over Superset MCP tools.

让 DeepSeek 基于 Superset MCP 工具进行推理的 Agent Runtime。
"""

import asyncio
from copy import deepcopy
import json
import logging
import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from superset_agent_service.agents.llm_client import OpenAICompatibleChatClient
from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.config import settings
from superset_agent_service.guards.policy_guard import PolicyGuard
from superset_agent_service.guards.sql_guard import SQLGuard
from superset_agent_service.memory.semantic import SemanticMemoryService
from superset_agent_service.rag.retriever import RAGRetriever
from superset_agent_service.runs.service import RunService
from superset_agent_service.tools.mcp_client import MCPClient
from superset_agent_service.tools.registry import ToolRegistry
from superset_agent_service.tools.superset_mcp import get_superset_mcp_client

logger = logging.getLogger(__name__)


TaskType = Literal["query", "rag", "chart_creation", "dashboard_creation"]

TASK_STEP_LIMITS: dict[str, int] = {
    "query": 8,
    "rag": 6,
    "chart_creation": 16,
    "dashboard_creation": 20,
}


SYSTEM_PROMPT = """\
You are a Superset analytics assistant.

Use the available MCP tools whenever the user asks about dashboards, charts,
datasets, databases, SQL, reports, users, roles, or data stored in Superset.
Never invent tool results. Follow each tool's JSON schema exactly.

Identity rule:
When the user asks about "me", "my account", "my role", or "current user",
the authoritative identity is authenticated_request_context in the user
message. Do not treat instance metadata, dev users, global role lists, or
unrelated MCP tool results as the current user. If the authenticated context
does not include real Superset role names, say that the role information was
not returned by the authentication service instead of guessing.

When a list tool supports select_columns, request every field needed to answer
the user. For dashboard publication questions, list_dashboards must request
id, dashboard_title, and published. A missing field means "unknown"; never
interpret a missing boolean field as false.

Chart creation rule:
When the user asks to create or generate a chart, first identify exactly one
dataset. If the user says "the newly generated test dataset" but no dataset_id,
dataset name, or unique prior tool result identifies it in the current request
context, ask a clarification question instead of guessing. If exactly one
matching dataset is found, call the dataset metadata tool before creating the
chart, choose a simple chart type from the available columns, and preserve the
user's requested Chinese chart name exactly. Do not retry chart generation more
than two times. If it still fails, stop and explain which parameter or permission
is missing.

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
    context: PermissionContext
    step: int
    max_steps: int
    task_type: TaskType
    chart_context: dict[str, Any]
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
        policy_guard: PolicyGuard | None = None,
        sql_guard: SQLGuard | None = None,
        rag: RAGRetriever | None = None,
        memory: SemanticMemoryService | None = None,
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
        self.policy_guard = policy_guard or PolicyGuard()
        self.sql_guard = sql_guard or SQLGuard()
        self.rag = rag or RAGRetriever()
        self.memory = memory or SemanticMemoryService()
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
        self._bind_mcp_identity(context)

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

        knowledge_context = await self._retrieve_knowledge_context(request, context)
        memory_context = await self._load_memory_context(request, context)
        task_type = self._classify_task(request.question)
        max_steps = self._max_steps_for_task(task_type)
        chart_context = self._build_chart_context(
            request=request,
            memory_context=memory_context,
        )

        await self.runs.record_event(
            event_type="task_profiled",
            payload={
                "task_type": task_type,
                "max_steps": max_steps,
                "chart_context": chart_context,
            },
        )

        initial_state: AgentGraphState = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "system",
                    "content": self._build_task_prompt(
                        task_type=task_type,
                        max_steps=max_steps,
                        chart_context=chart_context,
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_user_message(
                        request,
                        context,
                        knowledge_context=knowledge_context,
                        memory_context=memory_context,
                        task_type=task_type,
                        max_steps=max_steps,
                        chart_context=chart_context,
                    ),
                },
            ],
            "model_tools": model_tools,
            "pending_tool_calls": [],
            "context": context,
            "step": 0,
            "max_steps": max_steps,
            "task_type": task_type,
            "chart_context": chart_context,
            "answer": None,
        }

        final_state = await self.graph.ainvoke(
            initial_state,
            # Each reasoning round visits model -> tools.  The small buffer also
            # allows the final model -> END transition without hitting the
            # framework's recursion guard.
            # 每轮推理都会经过 model -> tools；额外缓冲允许最后一次 model -> END
            # 转换完成，而不会触发框架的递归保护限制。
            config={"recursion_limit": max_steps * 2 + 2},
        )
        answer = final_state.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("LangGraph completed without a final answer")
        await self._remember_final_answer(
            request=request,
            context=context,
            answer=answer.strip(),
        )
        return answer.strip()

    async def _load_memory_context(
        self,
        request: AgentRequest,
        context: PermissionContext,
    ) -> dict[str, Any]:
        """Load semantically similar long-term memory for this user.

        加载当前用户语义相似的长期记忆。
        """

        try:
            memory_context = await self.memory.get_runtime_context(
                query=request.question,
                context=context,
            )
        except Exception as exc:
            logger.warning(
                "Memory loading failed: user_id=%s username=%s error=%s",
                context.user_id,
                context.username,
                exc,
            )
            await self.runs.record_event(
                event_type="memory_failed",
                payload={"operation": "load", "error": str(exc)},
            )
            return {}
        if any(memory_context.values()):
            await self.runs.record_event(
                event_type="memory_loaded",
                payload={
                    "semantic_conversation_count": len(
                        memory_context.get("semantic_conversations", [])
                    ),
                },
            )
        return memory_context

    async def _remember_final_answer(
        self,
        *,
        request: AgentRequest,
        context: PermissionContext,
        answer: str,
    ) -> None:
        """Vectorize and persist the latest user question and final answer.

        将最近一次用户问题和最终回答向量化写入长期记忆。
        """

        try:
            memory_id = await self.memory.remember_conversation(
                context=context,
                question=request.question,
                answer=answer,
                run_id=self.runs.run_id,
            )
            await self.runs.record_event(
                event_type="memory_written",
                payload={
                    "memory_type": "semantic_conversation",
                    "memory_id": memory_id,
                },
            )
        except Exception as exc:
            logger.warning(
                "Memory final-answer write failed: user_id=%s username=%s error=%s",
                context.user_id,
                context.username,
                exc,
            )
            await self.runs.record_event(
                event_type="memory_failed",
                payload={"operation": "remember_final_answer", "error": str(exc)},
            )

    async def _retrieve_knowledge_context(
        self,
        request: AgentRequest,
        context: PermissionContext,
    ) -> list[dict[str, object]]:
        """Search RAG knowledge before the model starts reasoning.

        在模型开始推理前检索 RAG 知识库。
        """

        try:
            results = await self.rag.search(request.question, context=context)
        except Exception as exc:
            logger.warning(
                "RAG retrieval failed: user_id=%s username=%s error=%s",
                context.user_id,
                context.username,
                exc,
            )
            await self.runs.record_event(
                event_type="rag_failed",
                payload={"error": str(exc)},
            )
            return []
        if results:
            await self.runs.record_event(
                event_type="rag_retrieved",
                payload={
                    "count": len(results),
                    "documents": [
                        {
                            "document_id": result.get("document_id"),
                            "filename": result.get("filename"),
                            "score": result.get("score"),
                        }
                        for result in results
                    ],
                },
            )
        return results

    def _bind_mcp_identity(self, context: PermissionContext) -> None:
        """Attach the current user's bearer token to the MCP client when possible.

        尽可能把当前用户的 Bearer Token 绑定到 MCP 客户端，避免用默认身份查询 Superset 数据。
        """

        if not context.mcp_bearer_token or self.mcp is None:
            return
        if hasattr(self.mcp, "bearer_token"):
            self.mcp.bearer_token = context.mcp_bearer_token
            logger.info(
                "Bound MCP bearer token for user_id=%s username=%s",
                context.user_id,
                context.username,
            )

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
        max_steps = state["max_steps"]
        if step > max_steps:
            raise RuntimeError(
                f"Agent reached max_steps={max_steps} for "
                f"task_type={state['task_type']} without producing a final answer"
            )

        assistant_message = await self.llm.complete(
            state["messages"],
            state["model_tools"],
            on_content_delta=self._publish_answer_delta,
        )
        await self._record_model_usage(assistant_message)
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
            tool_messages.append(
                await self._execute_tool_call(
                    tool_call=tool_call,
                    context=state["context"],
                )
            )

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

    async def _record_model_usage(self, assistant_message: dict[str, Any]) -> None:
        """Persist model usage metrics when the provider includes them.

        当模型服务返回用量信息时，将其持久化到运行记录。
        """

        usage = assistant_message.get("_usage")
        if not isinstance(usage, dict):
            return
        await self.runs.record_model_usage(
            input_tokens=self._optional_int(usage.get("prompt_tokens")),
            output_tokens=self._optional_int(usage.get("completion_tokens")),
            total_tokens=self._optional_int(usage.get("total_tokens")),
        )

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        """Convert provider usage values to integers when possible.

        在可能时将模型服务返回的用量值转换为整数。
        """

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        return None

    async def _execute_tool_call(
        self,
        tool_call: dict[str, Any],
        context: PermissionContext,
    ) -> dict[str, Any]:
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

        logger.info(
            "Runtime tool requested: user_id=%s username=%s tool=%s arguments=%s",
            context.user_id,
            context.username,
            name,
            self._summarize_for_log(arguments),
        )

        if not self.policy_guard.can_use_tool(context=context, tool_name=name):
            content = json.dumps(
                {
                    "error": f"Permission denied for tool {name}",
                    "tool": name,
                },
                ensure_ascii=False,
            )
            await self.runs.record_event(
                event_type="tool_blocked",
                payload={
                    "tool": name,
                    "reason": "permission_denied",
                    "user_id": context.user_id,
                    "username": context.username,
                    "roles": context.roles,
                    "allowed_tools": context.allowed_tools,
                },
            )
            return self._tool_message(call_id=call_id, name=name, content=content)

        try:
            guarded_arguments, sql_rewrite_events = self._guard_sql_arguments(
                tool_name=name,
                arguments=arguments,
            )
        except RuntimeError as exc:
            content = json.dumps(
                {"error": str(exc), "tool": name},
                ensure_ascii=False,
            )
            await self.runs.record_event(
                event_type="tool_failed",
                payload={"tool": name, "error": str(exc)},
            )
            return self._tool_message(call_id=call_id, name=name, content=content)

        for path in sql_rewrite_events:
            await self._record_sql_event(
                event_type="sql_guard_rewritten",
                tool_name=name,
                path=path,
                detail={"max_rows": settings.MAX_SQL_ROWS},
            )

        await self.runs.record_event(
            event_type="tool_started",
            payload={"tool": name, "arguments": guarded_arguments},
        )

        try:
            logger.info(
                "Calling MCP tool: user_id=%s username=%s tool=%s arguments=%s",
                context.user_id,
                context.username,
                name,
                self._summarize_for_log(guarded_arguments),
            )
            result = await self.mcp.call_tool(name, guarded_arguments)
            logger.info(
                "MCP tool completed: user_id=%s username=%s tool=%s result=%s",
                context.user_id,
                context.username,
                name,
                self._summarize_for_log(result),
            )
            content = json.dumps(result, ensure_ascii=False, default=str)
            await self.runs.record_event(
                event_type="tool_completed",
                payload={
                    "tool": name,
                    "result_summary": self._summarize_for_log(result),
                },
            )
        except Exception as exc:
            logger.exception(
                "MCP tool failed: user_id=%s username=%s tool=%s",
                context.user_id,
                context.username,
                name,
            )
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

        return self._tool_message(call_id=call_id, name=name, content=content)

    def _guard_sql_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[dict[str, Any], list[tuple[str, ...]]]:
        """Validate and rewrite SQL-bearing tool arguments before MCP execution.

        在执行 MCP 前校验并改写包含 SQL 的工具参数。
        """

        guarded = deepcopy(arguments)
        rewritten_paths: list[tuple[str, ...]] = []

        def visit(value: Any, path: tuple[str, ...]) -> Any:
            if isinstance(value, dict):
                for key, nested_value in list(value.items()):
                    next_path = (*path, str(key))
                    if self._is_sql_argument_key(str(key)) and isinstance(
                        nested_value,
                        str,
                    ):
                        value[key], rewritten = self._validate_sql_value(
                            tool_name=tool_name,
                            sql=nested_value,
                            path=next_path,
                        )
                        if rewritten:
                            rewritten_paths.append(next_path)
                    else:
                        value[key] = visit(nested_value, next_path)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    value[index] = visit(item, (*path, str(index)))
            return value

        return visit(guarded, ()), rewritten_paths

    async def _record_sql_event(
        self,
        event_type: str,
        tool_name: str,
        path: tuple[str, ...],
        detail: dict[str, object],
    ) -> None:
        """Record one SQL guard decision using a stable event payload.

        使用稳定的事件载荷记录一次 SQL Guard 决策。
        """

        await self.runs.record_event(
            event_type=event_type,
            payload={
                "tool": tool_name,
                "argument_path": ".".join(path),
                **detail,
            },
        )

    def _validate_sql_value(
        self,
        tool_name: str,
        sql: str,
        path: tuple[str, ...],
    ) -> tuple[str, bool]:
        """Return safe SQL or raise a clear error for the model to observe.

        返回安全 SQL；不安全时抛出清晰错误供模型观察。
        """

        result = self.sql_guard.validate(sql)
        if not result.allowed:
            raise RuntimeError(
                f"SQLGuard blocked SQL for {tool_name} at {'.'.join(path)}: "
                f"{result.reason}"
            )
        rewritten_sql = result.rewritten_sql or sql
        return rewritten_sql, rewritten_sql != sql

    @staticmethod
    def _is_sql_argument_key(key: str) -> bool:
        """Identify argument names that are intended to carry executable SQL.

        识别用于承载可执行 SQL 的参数名。
        """

        normalized = key.lower()
        return normalized in {"sql", "sql_query", "query_sql", "statement"}

    def _summarize_for_log(self, value: Any, max_length: int = 1200) -> str:
        """Serialize and truncate values before writing them to logs.

        在写入日志前序列化并截断内容，避免大结果刷爆终端。
        """

        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
        if len(text) <= max_length:
            return text
        return f"{text[:max_length]}...<truncated>"

    @staticmethod
    def _tool_message(call_id: str, name: str, content: str) -> dict[str, Any]:
        """Build the OpenAI-compatible tool message returned to the model.

        构造返回给模型的 OpenAI 兼容 tool 消息。
        """

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

    @classmethod
    def _classify_task(cls, question: str) -> TaskType:
        """Classify a user request into a small runtime strategy bucket.

        将用户请求归类到少量运行时策略类型中。
        """

        normalized = question.strip().lower()
        chart_terms = (
            "生成图表",
            "创建图表",
            "新建图表",
            "画图",
            "画一个图",
            "做图",
            "建图",
            "chart",
            "visualization",
        )
        dashboard_terms = (
            "生成仪表盘",
            "创建仪表盘",
            "新建仪表盘",
            "创建看板",
            "生成看板",
            "dashboard",
        )
        rag_terms = (
            "知识库",
            "文档",
            "文件",
            "资料",
            "上传",
            "pdf",
            "word",
            "excel",
            "rag",
        )
        creation_verbs = ("创建", "生成", "新建", "create", "generate", "build")
        if any(term in normalized for term in dashboard_terms) or (
            any(verb in normalized for verb in creation_verbs)
            and any(noun in normalized for noun in ("看板", "仪表盘"))
        ):
            return "dashboard_creation"
        if any(term in normalized for term in chart_terms) or (
            any(verb in normalized for verb in creation_verbs)
            and any(noun in normalized for noun in ("图表", "图", "chart"))
        ):
            return "chart_creation"
        if any(term in normalized for term in rag_terms):
            return "rag"
        return "query"

    @staticmethod
    def _max_steps_for_task(task_type: TaskType) -> int:
        """Return a task-specific step budget.

        返回按任务类型区分的步数预算。
        """

        return TASK_STEP_LIMITS[task_type]

    @classmethod
    def _build_task_prompt(
        cls,
        *,
        task_type: TaskType,
        max_steps: int,
        chart_context: dict[str, Any],
    ) -> str:
        """Build a narrow strategy prompt for the classified task.

        为已分类任务构建更窄的策略提示。
        """

        base = (
            f"Runtime task profile: task_type={task_type}, max_steps={max_steps}. "
            "Stay inside this step budget and stop with a clear question if the "
            "required resource cannot be identified."
        )
        if task_type != "chart_creation":
            return base

        return (
            f"{base}\n"
            "Chart workflow:\n"
            "1. Use chart_context.last_dataset_id when present. Do not search for "
            "another dataset unless the user explicitly asks for a different one.\n"
            "2. If the user refers to a newly generated, previous, or current "
            "dataset and chart_context has no last_dataset_id, ask for the dataset "
            "ID or name instead of guessing.\n"
            "3. Read dataset metadata at most once before generate_chart.\n"
            "4. Preserve the requested Chinese chart name exactly.\n"
            "5. Retry generate_chart at most once after a parameter/schema error. "
            "For permission errors, stop and explain the permission issue.\n"
            "chart_context:\n"
            f"{json.dumps(chart_context, ensure_ascii=False, default=str)}"
        )

    @classmethod
    def _build_chart_context(
        cls,
        *,
        request: AgentRequest,
        memory_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract the latest Superset resource references for chart creation.

        提取建图任务可复用的最近 Superset 资源引用。
        """

        context: dict[str, Any] = {
            "last_dataset_id": None,
            "last_dataset_name": None,
            "last_chart_id": request.chart_id,
            "last_dashboard_id": request.dashboard_id,
            "source": None,
            "needs_dataset_clarification": False,
        }

        cls._merge_resource_refs(context, request.filters, source="request.filters")
        conversations = memory_context.get("semantic_conversations")
        if isinstance(conversations, list):
            for item in conversations:
                if not isinstance(item, dict):
                    continue
                cls._merge_resource_refs(context, item, source="semantic_memory")
                for key in ("answer", "text", "question"):
                    value = item.get(key)
                    if isinstance(value, str):
                        cls._merge_resource_refs(
                            context,
                            cls._extract_resource_refs_from_text(value),
                            source="semantic_memory",
                        )

        if cls._uses_recent_reference(request.question) and not context["last_dataset_id"]:
            context["needs_dataset_clarification"] = True
        return context

    @classmethod
    def _merge_resource_refs(
        cls,
        target: dict[str, Any],
        value: Any,
        *,
        source: str,
    ) -> None:
        """Merge known Superset resource IDs into a compact context object.

        将已知 Superset 资源 ID 合并到紧凑上下文对象中。
        """

        for item in cls._walk_mappings(value):
            lowered = {str(key).lower(): key for key in item}
            dataset_id = cls._first_value(
                item,
                lowered,
                ("dataset_id", "datasource_id"),
            )
            chart_id = cls._first_value(item, lowered, ("chart_id", "slice_id"))
            dashboard_id = cls._first_value(item, lowered, ("dashboard_id",))
            dataset_name = cls._first_value(
                item,
                lowered,
                ("dataset_name", "table_name", "name"),
            )
            if dataset_id and not target.get("last_dataset_id"):
                target["last_dataset_id"] = str(dataset_id)
                target["source"] = source
            if dataset_name and not target.get("last_dataset_name"):
                target["last_dataset_name"] = str(dataset_name)
            if chart_id and not target.get("last_chart_id"):
                target["last_chart_id"] = str(chart_id)
            if dashboard_id and not target.get("last_dashboard_id"):
                target["last_dashboard_id"] = str(dashboard_id)

    @staticmethod
    def _extract_resource_refs_from_text(text: str) -> dict[str, Any]:
        """Extract common resource IDs from natural-language memories.

        从自然语言记忆文本中提取常见资源 ID。
        """

        refs: dict[str, Any] = {}
        patterns = {
            "dataset_id": (
                r'"dataset_id"\s*:\s*"?(\d+)"?',
                r"\bdataset[_\s-]*id\s*[:=：]?\s*(\d+)",
                r"数据集\s*(?:id|ID)?\s*[:=：]?\s*(\d+)",
            ),
            "chart_id": (
                r'"chart_id"\s*:\s*"?(\d+)"?',
                r"\bchart[_\s-]*id\s*[:=：]?\s*(\d+)",
                r"图表\s*(?:id|ID)?\s*[:=：]?\s*(\d+)",
            ),
            "dashboard_id": (
                r'"dashboard_id"\s*:\s*"?(\d+)"?',
                r"\bdashboard[_\s-]*id\s*[:=：]?\s*(\d+)",
                r"(?:仪表盘|看板)\s*(?:id|ID)?\s*[:=：]?\s*(\d+)",
            ),
        }
        for key, key_patterns in patterns.items():
            for pattern in key_patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    refs[key] = match.group(1)
                    break
        return refs

    @staticmethod
    def _uses_recent_reference(question: str) -> bool:
        """Return whether the user refers to a recent implicit resource.

        判断用户是否引用了最近生成或上一个隐式资源。
        """

        normalized = question.lower()
        return any(
            term in normalized
            for term in (
                "刚生成",
                "刚才",
                "上一个",
                "这个数据集",
                "该数据集",
                "当前数据集",
                "newly generated",
                "previous dataset",
                "this dataset",
            )
        )

    @classmethod
    def _walk_mappings(cls, value: Any) -> list[dict[str, Any]]:
        """Return all dictionaries nested inside a JSON-like value.

        返回 JSON 类值中嵌套的所有字典。
        """

        if isinstance(value, dict):
            found = [value]
            for nested in value.values():
                found.extend(cls._walk_mappings(nested))
            return found
        if isinstance(value, list):
            found: list[dict[str, Any]] = []
            for item in value:
                found.extend(cls._walk_mappings(item))
            return found
        return []

    @staticmethod
    def _first_value(
        item: dict[str, Any],
        lowered_keys: dict[str, Any],
        candidates: tuple[str, ...],
    ) -> Any:
        """Return the first non-empty value among case-insensitive keys.

        按大小写不敏感字段名返回第一个非空值。
        """

        for candidate in candidates:
            key = lowered_keys.get(candidate)
            if key is not None and item.get(key) not in (None, ""):
                return item.get(key)
        return None

    @staticmethod
    def _build_user_message(
        request: AgentRequest,
        context: PermissionContext,
        knowledge_context: list[dict[str, object]] | None = None,
        memory_context: dict[str, Any] | None = None,
        task_type: TaskType = "query",
        max_steps: int | None = None,
        chart_context: dict[str, Any] | None = None,
    ) -> str:
        """Combine the question with optional UI context without changing it.

        在不改写用户问题的前提下，附加可选的界面上下文。
        """

        supplemental = {
            "dashboard_id": request.dashboard_id,
            "chart_id": request.chart_id,
            "filters": request.filters,
            "time_range": request.time_range,
            "authenticated_request_context": {
                "user_id": context.user_id,
                "username": context.username,
                "roles": context.roles,
                "allowed_tools": context.allowed_tools,
                "allowed_dataset_ids": context.allowed_dataset_ids,
            },
            "retrieved_knowledge": knowledge_context or [],
            "long_term_memory": memory_context or {},
            "task_profile": {
                "task_type": task_type,
                "max_steps": max_steps,
            },
            "chart_context": chart_context or {},
        }
        return (
            f"User question:\n{request.question}\n\n"
            "Optional request context (null values can be ignored):\n"
            f"{json.dumps(supplemental, ensure_ascii=False, default=str)}"
        )
