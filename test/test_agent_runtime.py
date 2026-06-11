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
from superset_agent_service.runs.service import RunService
from superset_agent_service.tools.registry import ToolRegistry


class FakeLLM:
    """Return a tool call first and a final answer after receiving its result.

    第一次返回工具调用，收到工具结果后再返回最终答案。
    """

    def __init__(self) -> None:
        """Track invocation count and every conversation sent by the Runtime.

        记录调用次数以及 Runtime 发送的每组对话。
        """

        self.calls = 0
        self.received_messages = []

    async def complete(self, messages, tools, on_content_delta=None):
        """Simulate the two model turns required by a tool-calling workflow.

        模拟工具调用流程所需的两轮模型响应。
        """

        self.calls += 1
        self.received_messages.append(list(messages))
        if self.calls == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "list_dashboards",
                            "arguments": '{"request":{"page":1}}',
                        },
                    }
                ],
            }
        answer = "找到 1 个仪表盘。"
        if on_content_delta is not None:
            await on_content_delta(answer)
        return {"role": "assistant", "content": answer}


class FakeMCP:
    """Provide a deterministic in-memory MCP server replacement.

    提供一个行为确定的内存 MCP 服务替身。
    """

    def __init__(self) -> None:
        """Collect tool calls so assertions can verify exact arguments.

        收集工具调用，便于断言精确参数。
        """

        self.calls = []

    async def list_tools(self):
        """Expose one dashboard tool with a representative input schema.

        暴露一个带有典型输入 Schema 的仪表盘工具。
        """

        return [
            {
                "name": "list_dashboards",
                "description": "List dashboards",
                "inputSchema": {
                    "type": "object",
                    "properties": {"request": {"type": "object"}},
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
