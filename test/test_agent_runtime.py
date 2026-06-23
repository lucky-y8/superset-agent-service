"""Unit tests for the DeepSeek-to-MCP Runtime loop.

DeepSeek 到 MCP Runtime 循环的单元测试。
"""

import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from superset_agent_service.agents.runtime import LangGraphRuntime
from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.db.base import Base
from superset_agent_service.guards.sql_guard import SQLGuard
from superset_agent_service.runs.service import RunService
from superset_agent_service.tools.registry import ToolRegistry


class FakeLLM:
    """Return a tool call first and a final answer after receiving its result.

    第一次返回工具调用，收到工具结果后再返回最终答案。
    """

    def __init__(
        self,
        tool_name: str = "list_dashboards",
        tool_arguments: str = '{"request":{"page":1}}',
        final_answer: str = "找到 1 个仪表盘。",
        usage_sequence: list[dict[str, int]] | None = None,
    ) -> None:
        """Track invocation count and every conversation sent by the Runtime.

        记录调用次数以及 Runtime 发送的每组对话。
        """

        self.calls = 0
        self.received_messages = []
        self.tool_name = tool_name
        self.tool_arguments = tool_arguments
        self.final_answer = final_answer
        self.usage_sequence = usage_sequence or []

    async def complete(self, messages, tools, on_content_delta=None):
        """Simulate the two model turns required by a tool-calling workflow.

        模拟工具调用流程所需的两轮模型响应。
        """

        self.calls += 1
        self.received_messages.append(list(messages))
        if self.calls == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": self.tool_name,
                            "arguments": self.tool_arguments,
                        },
                    }
                ],
            }
            self._attach_usage(message)
            return message
        if on_content_delta is not None:
            await on_content_delta(self.final_answer)
        message = {"role": "assistant", "content": self.final_answer}
        self._attach_usage(message)
        return message

    def _attach_usage(self, message: dict[str, object]) -> None:
        """Attach deterministic usage data for Runtime persistence tests.

        为 Runtime 持久化测试附加确定性的用量数据。
        """

        index = self.calls - 1
        if index < len(self.usage_sequence):
            message["_usage"] = self.usage_sequence[index]


class FakeMCP:
    """Provide a deterministic in-memory MCP server replacement.

    提供一个行为确定的内存 MCP 服务替身。
    """

    def __init__(self, tool_name: str = "list_dashboards") -> None:
        """Collect tool calls so assertions can verify exact arguments.

        收集工具调用，便于断言精确参数。
        """

        self.calls = []
        self.tool_name = tool_name

    async def list_tools(self):
        """Expose one dashboard tool with a representative input schema.

        暴露一个带有典型输入 Schema 的仪表盘工具。
        """

        return [
            {
                "name": self.tool_name,
                "description": f"Call {self.tool_name}",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "object",
                            "properties": {
                                "page": {"type": "integer"},
                                "sql": {"type": "string"},
                            },
                        }
                    },
                },
            }
        ]

    async def call_tool(self, name, arguments):
        """Record and return a fixed successful tool result.

        记录调用并返回固定的成功工具结果。
        """

        self.calls.append((name, arguments))
        return {
            "content": [
                {"type": "text", "text": '{"dashboards":[{"id":1,"title":"Sales"}]}'}
            ]
        }


class FakeRAG:
    """Return no knowledge so Runtime unit tests never call external RAG services.

    返回空知识结果，确保 Runtime 单元测试不会调用外部 RAG 服务。
    """

    async def search(self, query, *, context, limit=None):
        """Match the RAGRetriever interface used by the Runtime.

        匹配 Runtime 使用的 RAGRetriever 接口。
        """

        return []


class FakeSemanticMemory:
    """Keep Runtime tests away from real embedding and Qdrant services.

    让 Runtime 测试不触发真实 Embedding 和 Qdrant 服务。
    """

    def __init__(
        self,
        runtime_context: dict[str, object] | None = None,
    ) -> None:
        """Track stored conversations for assertions or debugging.

        记录写入的对话，便于断言或调试。
        """

        self.conversations = []
        self.runtime_context = runtime_context or {"semantic_conversations": []}

    async def get_runtime_context(self, *, query, context, limit=None):
        """Return no semantic memories by default.

        默认不返回语义记忆。
        """

        return self.runtime_context

    async def remember_conversation(self, *, context, question, answer, run_id=None):
        """Record the conversation without external calls.

        记录对话但不调用外部服务。
        """

        self.conversations.append(
            {
                "user_id": context.user_id,
                "question": question,
                "answer": answer,
                "run_id": run_id,
            }
        )
        return "memory-1"


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """Verify Runtime graph behavior without external network services.

    在不依赖外部网络服务的情况下验证 Runtime 图行为。
    """

    async def asyncSetUp(self) -> None:
        """Create an isolated database schema for each asynchronous test.

        为每个异步测试创建相互隔离的数据库结构。
        """

        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        """Dispose the isolated database engine after each test.

        每个测试结束后释放隔离数据库引擎。
        """

        await self.engine.dispose()

    async def test_runtime_executes_mcp_tool_and_returns_final_answer(self):
        """Confirm one complete model-tool-model cycle and its trace events.

        验证一次完整的“模型-工具-模型”循环及其轨迹事件。
        """

        runs = RunService(session_factory=self.sessions)
        runs.bind_run("test-run", "local-user")
        await runs.start_run(
            AgentRequest(question="列出仪表盘"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )
        llm = FakeLLM()
        mcp = FakeMCP()
        runtime = LangGraphRuntime(
            tools=ToolRegistry.default(),
            runs=runs,
            llm=llm,
            mcp=mcp,
            rag=FakeRAG(),
            memory=FakeSemanticMemory(),
        )

        answer = await runtime.invoke(
            AgentRequest(question="有哪些仪表盘？"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )

        self.assertEqual(answer, "找到 1 个仪表盘。")
        self.assertEqual(
            mcp.calls,
            [("list_dashboards", {"request": {"page": 1}})],
        )
        self.assertEqual(llm.received_messages[1][-1]["role"], "tool")

        trace = await RunService.get_trace("test-run", self.sessions)
        self.assertIsNotNone(trace)
        event_types = [event.event_type for event in trace.events]
        self.assertIn("tools_discovered", event_types)
        self.assertIn("tool_completed", event_types)
        self.assertIn("answer_generated", event_types)

    async def test_runtime_accumulates_model_usage_when_provider_returns_it(self):
        """Confirm provider usage is accumulated on the persisted run.

        验证模型服务返回的用量会累加保存到运行记录。
        """

        runs = RunService(session_factory=self.sessions)
        runs.bind_run("usage-run", "local-user")
        await runs.start_run(
            AgentRequest(question="列出仪表盘"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )
        llm = FakeLLM(
            usage_sequence=[
                {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                {"prompt_tokens": 20, "completion_tokens": 7, "total_tokens": 27},
            ]
        )
        runtime = LangGraphRuntime(
            tools=ToolRegistry.default(),
            runs=runs,
            llm=llm,
            mcp=FakeMCP(),
            rag=FakeRAG(),
            memory=FakeSemanticMemory(),
        )

        await runtime.invoke(
            AgentRequest(question="有哪些仪表盘？"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )

        trace = await RunService.get_trace("usage-run", self.sessions)
        self.assertEqual(trace.input_tokens, 30)
        self.assertEqual(trace.output_tokens, 12)
        self.assertEqual(trace.total_tokens, 42)

    async def test_runtime_blocks_tool_when_policy_denies_access(self):
        """Confirm non-admin users cannot execute tools outside their allow-list.

        验证非管理员不能执行白名单之外的工具。
        """

        runs = RunService(session_factory=self.sessions)
        runs.bind_run("policy-denied-run", "viewer-user")
        await runs.start_run(
            AgentRequest(question="列出仪表盘"),
            PermissionContext(user_id="viewer-user", roles=["viewer"]),
        )
        llm = FakeLLM(final_answer="权限不足，无法调用工具。")
        mcp = FakeMCP()
        runtime = LangGraphRuntime(
            tools=ToolRegistry.default(),
            runs=runs,
            llm=llm,
            mcp=mcp,
            rag=FakeRAG(),
            memory=FakeSemanticMemory(),
        )

        answer = await runtime.invoke(
            AgentRequest(question="有哪些仪表盘？"),
            PermissionContext(user_id="viewer-user", roles=["viewer"]),
        )

        self.assertEqual(answer, "权限不足，无法调用工具。")
        self.assertEqual(mcp.calls, [])
        tool_message = llm.received_messages[1][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertIn("Permission denied", tool_message["content"])

        trace = await RunService.get_trace("policy-denied-run", self.sessions)
        event_types = [event.event_type for event in trace.events]
        self.assertIn("tool_blocked", event_types)

    async def test_runtime_allows_non_admin_tool_from_allow_list(self):
        """Confirm explicit tool allow-lists let non-admin users execute tools.

        验证明示工具白名单允许非管理员执行指定工具。
        """

        runs = RunService(session_factory=self.sessions)
        runs.bind_run("policy-allowed-run", "analyst-user")
        await runs.start_run(
            AgentRequest(question="列出仪表盘"),
            PermissionContext(user_id="analyst-user", roles=["analyst"]),
        )
        llm = FakeLLM()
        mcp = FakeMCP()
        runtime = LangGraphRuntime(
            tools=ToolRegistry.default(),
            runs=runs,
            llm=llm,
            mcp=mcp,
            rag=FakeRAG(),
            memory=FakeSemanticMemory(),
        )

        await runtime.invoke(
            AgentRequest(question="有哪些仪表盘？"),
            PermissionContext(
                user_id="analyst-user",
                roles=["analyst"],
                allowed_tools=["list_dashboards"],
            ),
        )

        self.assertEqual(
            mcp.calls,
            [("list_dashboards", {"request": {"page": 1}})],
        )

    async def test_runtime_treats_admin_role_case_insensitively(self):
        """Confirm Superset-style ``Admin`` role names can execute tools.

        验证 Superset 风格的 ``Admin`` 角色名也可以执行工具。
        """

        runs = RunService(session_factory=self.sessions)
        runs.bind_run("admin-case-run", "local-user")
        await runs.start_run(
            AgentRequest(question="列出仪表盘"),
            PermissionContext(user_id="local-user", roles=["Admin"]),
        )
        mcp = FakeMCP()
        runtime = LangGraphRuntime(
            tools=ToolRegistry.default(),
            runs=runs,
            llm=FakeLLM(),
            mcp=mcp,
            rag=FakeRAG(),
            memory=FakeSemanticMemory(),
        )

        await runtime.invoke(
            AgentRequest(question="有哪些仪表盘？"),
            PermissionContext(user_id="local-user", roles=["Admin"]),
        )

        self.assertEqual(
            mcp.calls,
            [("list_dashboards", {"request": {"page": 1}})],
        )

    async def test_chart_task_uses_semantic_memory_dataset_context(self):
        """Confirm chart tasks receive a compact dataset context from memory.

        验证建图任务会从语义记忆中获得紧凑的数据集上下文。
        """

        runs = RunService(session_factory=self.sessions)
        runs.bind_run("chart-context-run", "local-user")
        await runs.start_run(
            AgentRequest(question="Create a chart from the previous dataset"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )
        memory = FakeSemanticMemory(
            runtime_context={
                "semantic_conversations": [
                    {
                        "question": "Create test data",
                        "answer": "Created dataset_id: 42 named 测试销售数据",
                    }
                ]
            }
        )
        llm = FakeLLM(
            tool_name="get_dataset_info",
            tool_arguments='{"request":{"id":42}}',
            final_answer="已根据数据集 42 准备建图。",
        )
        runtime = LangGraphRuntime(
            tools=ToolRegistry.default(),
            runs=runs,
            llm=llm,
            mcp=FakeMCP(tool_name="get_dataset_info"),
            rag=FakeRAG(),
            memory=memory,
        )

        await runtime.invoke(
            AgentRequest(question="Create a chart from the previous dataset"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )

        first_messages = llm.received_messages[0]
        task_prompt = first_messages[1]["content"]
        user_prompt = first_messages[2]["content"]
        self.assertIn("task_type=chart_creation", task_prompt)
        self.assertIn('"last_dataset_id": "42"', task_prompt)
        self.assertIn('"task_type": "chart_creation"', user_prompt)
        self.assertIn('"last_dataset_id": "42"', user_prompt)

        trace = await RunService.get_trace("chart-context-run", self.sessions)
        event_types = [event.event_type for event in trace.events]
        self.assertIn("task_profiled", event_types)
        task_event = next(
            event for event in trace.events if event.event_type == "task_profiled"
        )
        self.assertEqual(task_event.payload["task_type"], "chart_creation")
        self.assertEqual(task_event.payload["max_steps"], 16)

    def test_task_classification_and_step_budgets_are_dynamic(self):
        """Confirm Runtime no longer uses one fixed step budget for all tasks.

        验证 Runtime 不再对所有任务使用同一个固定步数预算。
        """

        self.assertEqual(
            LangGraphRuntime._classify_task("根据刚生成的数据集生成图表"),
            "chart_creation",
        )
        self.assertEqual(
            LangGraphRuntime._classify_task("查询知识库里的部署文档"),
            "rag",
        )
        self.assertEqual(
            LangGraphRuntime._classify_task("创建一个新的看板"),
            "dashboard_creation",
        )
        self.assertEqual(LangGraphRuntime._max_steps_for_task("query"), 8)
        self.assertEqual(LangGraphRuntime._max_steps_for_task("rag"), 6)
        self.assertEqual(LangGraphRuntime._max_steps_for_task("chart_creation"), 16)
        self.assertEqual(
            LangGraphRuntime._max_steps_for_task("dashboard_creation"),
            20,
        )

    async def test_runtime_rewrites_sql_before_mcp_call(self):
        """Confirm SQLGuard clamps excessive LIMIT values before MCP execution.

        验证 SQLGuard 会在 MCP 执行前收紧过大的 LIMIT。
        """

        runs = RunService(session_factory=self.sessions)
        runs.bind_run("sql-rewrite-run", "local-user")
        await runs.start_run(
            AgentRequest(question="执行 SQL"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )
        llm = FakeLLM(
            tool_name="run_sql",
            tool_arguments='{"request":{"sql":"SELECT * FROM dashboards LIMIT 5000"}}',
        )
        mcp = FakeMCP(tool_name="run_sql")
        runtime = LangGraphRuntime(
            tools=ToolRegistry.default(),
            runs=runs,
            llm=llm,
            mcp=mcp,
            sql_guard=SQLGuard(max_rows=100),
            rag=FakeRAG(),
            memory=FakeSemanticMemory(),
        )

        await runtime.invoke(
            AgentRequest(question="执行 SQL"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )

        self.assertEqual(len(mcp.calls), 1)
        rewritten_sql = mcp.calls[0][1]["request"]["sql"]
        self.assertIn("LIMIT 100", rewritten_sql)

        trace = await RunService.get_trace("sql-rewrite-run", self.sessions)
        event_types = [event.event_type for event in trace.events]
        self.assertIn("sql_guard_rewritten", event_types)

    async def test_runtime_blocks_unsafe_sql_before_mcp_call(self):
        """Confirm unsafe SQL is returned as a tool error without calling MCP.

        验证危险 SQL 会以工具错误返回，并且不会真正调用 MCP。
        """

        runs = RunService(session_factory=self.sessions)
        runs.bind_run("sql-block-run", "local-user")
        await runs.start_run(
            AgentRequest(question="删除数据"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )
        llm = FakeLLM(
            tool_name="run_sql",
            tool_arguments='{"request":{"sql":"DELETE FROM dashboards"}}',
            final_answer="SQL 被安全策略拦截。",
        )
        mcp = FakeMCP(tool_name="run_sql")
        runtime = LangGraphRuntime(
            tools=ToolRegistry.default(),
            runs=runs,
            llm=llm,
            mcp=mcp,
            rag=FakeRAG(),
            memory=FakeSemanticMemory(),
        )

        answer = await runtime.invoke(
            AgentRequest(question="删除数据"),
            PermissionContext(user_id="local-user", roles=["admin"]),
        )

        self.assertEqual(answer, "SQL 被安全策略拦截。")
        self.assertEqual(mcp.calls, [])
        tool_message = llm.received_messages[1][-1]
        self.assertIn("SQLGuard blocked SQL", tool_message["content"])

        trace = await RunService.get_trace("sql-block-run", self.sessions)
        failed_events = [
            event
            for event in trace.events
            if event.event_type == "tool_failed"
        ]
        self.assertTrue(failed_events)

    def test_mcp_schema_is_converted_to_function_tool(self):
        """Confirm MCP schemas are translated into model function definitions.

        验证 MCP Schema 会被转换为模型函数定义。
        """

        converted = LangGraphRuntime._to_model_tools(
            [
                {
                    "name": "health_check",
                    "description": "Check service health",
                    "inputSchema": {"type": "object", "properties": {}},
                }
            ]
        )

        self.assertEqual(converted[0]["type"], "function")
        self.assertEqual(converted[0]["function"]["name"], "health_check")


if __name__ == "__main__":
    unittest.main()
