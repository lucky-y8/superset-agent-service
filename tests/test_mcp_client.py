r"""Tests for the MCP transport and the configured local MCP endpoint.

测试 MCP 传输层以及配置的本地 MCP 服务端点。

Deterministic transport tests do not require a running server. The live MCP
integration test runs only when ``RUN_MCP_INTEGRATION_TESTS=true`` is set, so a
developer's expired local token cannot make the normal unit-test suite fail.

确定性的传输层测试不需要启动服务。只有显式设置
``RUN_MCP_INTEGRATION_TESTS=true`` 时才执行在线 MCP 集成测试，避免开发机上的
过期 Token 导致常规单元测试失败。
"""

import asyncio
import os
import unittest

from superset_agent_service.tools.mcp_client import MCPClient, MCPError
from superset_agent_service.tools.superset_mcp import get_superset_mcp_client


class MCPResponseParsingTests(unittest.TestCase):
    """Verify response formats allowed by Streamable HTTP MCP.

    验证 Streamable HTTP MCP 支持的响应格式。
    """

    def test_parse_json_response(self) -> None:
        """Parse a normal JSON-RPC response body.

        解析普通的 JSON-RPC 响应正文。
        """

        message = MCPClient._parse_response(
            "application/json",
            '{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}',
        )

        self.assertEqual(message["result"]["tools"], [])

    def test_parse_sse_response(self) -> None:
        """Parse a JSON-RPC result wrapped in one SSE event.

        解析封装在单个 SSE 事件中的 JSON-RPC 结果。
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

        忽略最终结果之前的进度通知。
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
        """Allow arrays as tool results even when control methods use objects.

        即使控制方法使用对象，工具调用结果也可以是数组。
        """

        class StubClient(MCPClient):
            """Replace network I/O with one fixed JSON response.

            使用固定 JSON 响应替代真实网络 I/O。
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

    测试开发控制台实际使用的 MCP 服务端点。
    """

    async def test_initialize_configured_mcp_server(self) -> None:
        """Verify handshake and tool discovery in an explicitly enabled run.

        在明确启用在线测试后验证 MCP 握手和工具发现。
        """

        enabled = os.getenv("RUN_MCP_INTEGRATION_TESTS", "false").lower()
        if enabled not in {"1", "true", "yes"}:
            self.skipTest("set RUN_MCP_INTEGRATION_TESTS=true to run live MCP tests")

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
