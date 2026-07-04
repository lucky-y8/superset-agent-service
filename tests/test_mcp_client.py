r"""Tests for the MCP transport and the configured local MCP endpoint.

MCP 传输层和已配置本地 MCP 端点的测试。

The project does not yet depend on pytest, so these tests use Python's built-in
``unittest`` module.  They can be executed with:

    .venv\Scripts\python.exe -m unittest discover -s test -p "test_*.py"

项目目前没有依赖 pytest，因此这些测试使用 Python 内置的 ``unittest`` 模块，
并可通过上面的命令执行。

The first group is deterministic and does not need a running server.  The last
test is an integration check and is skipped when SUPERSET_MCP_URL is empty.

第一组测试行为确定，不需要启动服务；最后一个测试是集成检查，当
SUPERSET_MCP_URL 为空时会自动跳过。
"""

import asyncio
import unittest

from superset_agent_service.tools.mcp_client import MCPClient, MCPError
from superset_agent_service.tools.superset_mcp import get_superset_mcp_client


class MCPResponseParsingTests(unittest.TestCase):
    """Verify both response formats allowed by Streamable HTTP MCP.

    验证 Streamable HTTP MCP 允许的两种响应格式。
    """

    def test_parse_json_response(self) -> None:
        """Parse a normal JSON-RPC response body.

        解析普通 JSON-RPC 响应正文。
        """

        message = MCPClient._parse_response(
            "application/json",
            '{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}',
        )

        self.assertEqual(message["result"]["tools"], [])

    def test_parse_sse_response(self) -> None:
        """Parse a JSON-RPC result wrapped in one SSE event.

        解析包装在单个 SSE 事件中的 JSON-RPC 结果。
        """

        body = (
            "event: message\n"
            'data: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n'
            "\n"
        )

        message = MCPClient._parse_response("text/event-stream", body)

        self.assertEqual(message["result"]["tools"], [])

    def test_parse_sse_requires_data_event(self) -> None:
        """Reject an SSE stream that never carries a JSON-RPC result.

        拒绝始终没有携带 JSON-RPC 结果的 SSE 数据流。
        """

        with self.assertRaisesRegex(MCPError, "did not contain a JSON-RPC result"):
            MCPClient._parse_response("text/event-stream", "event: ping\n\n")

    def test_parse_sse_skips_notifications_before_result(self) -> None:
        """Ignore progress notifications that precede the final result.

        忽略最终结果之前出现的进度通知。
        """

        body = (
            "event: message\n"
            'data: {"jsonrpc":"2.0","method":"notifications/message",'
            '"params":{"level":"info"}}\n'
            "\n"
            "event: message\n"
            'data: {"jsonrpc":"2.0","id":2,"result":{"content":[]}}\n'
            "\n"
        )

        message = MCPClient._parse_response("text/event-stream", body)

        self.assertEqual(message["id"], 2)
        self.assertEqual(message["result"], {"content": []})

    def test_tool_call_accepts_non_object_json_result(self) -> None:
        """Tool results may be arrays even though control methods use objects.

        即使控制方法返回对象，工具结果也可以是数组。
        """

        class StubClient(MCPClient):
            """Replace network I/O with one fixed JSON response.

            用固定 JSON 响应替代真实网络 I/O。
            """

            def _post_json(self, headers, payload):
                """Return a simulated successful HTTP response.

                返回模拟的成功 HTTP 响应。
                """

                return (
                    "application/json",
                    '{"jsonrpc":"2.0","id":1,"result":[{"id":1}]}',
                )

        result = asyncio.run(
            StubClient("http://example.test/mcp").call_tool("list_items", {})
        )

        self.assertEqual(result, [{"id": 1}])


class ConfiguredMCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Exercise the same endpoint used by the development console.

    测试开发控制台实际使用的同一个 MCP 端点。
    """

    async def test_initialize_configured_mcp_server(self) -> None:
        """Verify handshake and tool discovery when local MCP is configured.

        在已配置本地 MCP 时验证握手和工具发现。
        """

        client = get_superset_mcp_client()
        if client is None:
            self.skipTest("SUPERSET_MCP_URL is not configured")

        initialization = await client.initialize()
        tools = await client.list_tools()

        self.assertIn("protocolVersion", initialization)
        self.assertIn("serverInfo", initialization)
        self.assertIsInstance(tools, list)


if __name__ == "__main__":
    unittest.main()
