"""WebSocket protocol tests for live Agent progress events.

Agent 实时进度事件的 WebSocket 协议测试。
"""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from superset_agent_service.agents.schemas import AgentResponse
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.main import app


class FakeStreamingAgentService:
    """Emit deterministic progress and token events without invoking a model.

    在不调用真实模型的情况下发送固定的进度和 Token 事件。
    """

    def __init__(self, event_sink=None):
        """Store the WebSocket event callback supplied by the API layer.

        保存 API 层传入的 WebSocket 事件回调。
        """

        self.event_sink = event_sink

    async def chat(self, request, context):
        """Simulate one successful streamed Agent request.

        模拟一次成功的流式 Agent 请求。
        """

        await self.event_sink(
            {
                "type": "run_event",
                "run_id": "run-1",
                "event": {
                    "event_type": "tool_started",
                    "payload": {"tool": "list_dashboards"},
                    "created_at": "2026-06-11T00:00:00Z",
                },
            }
        )
        await self.event_sink(
            {
                "type": "answer_delta",
                "run_id": "run-1",
                "payload": {"delta": "完成"},
            }
        )
        return AgentResponse(run_id="run-1", answer="完成", status="completed")


class AgentWebSocketTests(unittest.TestCase):
    """Verify the order and shape of messages sent to a browser.

    验证发送给浏览器的消息顺序和结构。
    """

    def test_socket_streams_progress_and_final_response(self):
        """Confirm progress, token delta, and final response arrive in order.

        验证进度、Token 增量和最终响应会按顺序到达。
        """

        with patch(
            "superset_agent_service.agents.api.AgentService",
            FakeStreamingAgentService,
        ), patch(
            "superset_agent_service.agents.api.settings.SUPERSET_AGENT_TOKEN_VERIFY_URL",
            None,
        ):
            with TestClient(app) as client:
                with client.websocket_connect("/api/v1/agents/ws") as socket:
                    self.assertEqual(socket.receive_json(), {"type": "connected"})
                    socket.send_json(
                        {
                            "type": "run",
                            "request": {
                                "question": "列出仪表盘",
                                "filters": {},
                            },
                            "context": {
                                "user_id": "local-user",
                                "tenant_id": "local",
                                "roles": ["admin"],
                            },
                        }
                    )

                    self.assertEqual(
                        socket.receive_json()["event"]["event_type"],
                        "tool_started",
                    )
                    self.assertEqual(
                        socket.receive_json()["payload"]["delta"],
                        "完成",
                    )
                    final = socket.receive_json()
                    self.assertEqual(final["type"], "final")
                    self.assertEqual(final["response"]["status"], "completed")

    def test_socket_uses_verified_token_context_when_configured(self):
        """Ensure production auth ignores browser-supplied identity fields.

        确认生产认证开启后，会忽略浏览器传入的身份字段。
        """

        captured_contexts = []

        class CapturingAgentService(FakeStreamingAgentService):
            """Capture the trusted context used by the API layer.

            捕获 API 层传给 Runtime 的可信上下文。
            """

            async def chat(self, request, context):
                """Record the context and return a deterministic response.

                记录权限上下文，并返回固定响应。
                """

                captured_contexts.append(context)
                return AgentResponse(run_id="run-2", answer="ok", status="completed")

        verified_context = PermissionContext(
            user_id="verified-user",
            roles=["authenticated"],
            allowed_tools=["list_dashboards"],
        )

        with patch(
            "superset_agent_service.agents.api.AgentService",
            CapturingAgentService,
        ), patch(
            "superset_agent_service.agents.api.settings.SUPERSET_AGENT_TOKEN_VERIFY_URL",
            "http://superset.local/api/v1/agent/token/verify",
        ), patch(
            "superset_agent_service.agents.api.token_verifier.verify",
            new=AsyncMock(return_value=verified_context),
        ) as verify:
            with TestClient(app) as client:
                with client.websocket_connect("/api/v1/agents/ws") as socket:
                    self.assertEqual(socket.receive_json(), {"type": "connected"})
                    socket.send_json(
                        {
                            "type": "run",
                            "token": "signed-token",
                            "request": {
                                "question": "list dashboards",
                                "filters": {},
                            },
                            "context": {
                                "user_id": "forged-admin",
                                "tenant_id": "local",
                                "roles": ["admin"],
                            },
                        }
                    )

                    final = socket.receive_json()
                    self.assertEqual(final["type"], "final")

        verify.assert_awaited_once_with("signed-token")
        self.assertEqual(captured_contexts[0].user_id, "verified-user")
        self.assertEqual(captured_contexts[0].roles, ["authenticated"])

    def test_socket_accepts_query_token_for_connection_auth(self):
        """Allow integrated Superset pages to authenticate the socket URL token.

        允许集成到 Superset 的页面通过 WebSocket URL Token 完成连接认证。
        """

        captured_contexts = []

        class CapturingAgentService(FakeStreamingAgentService):
            """Capture the authenticated context reused by the socket.

            捕获 WebSocket 复用的已认证上下文。
            """

            async def chat(self, request, context):
                """Record context and return a deterministic response.

                记录上下文并返回固定响应。
                """

                captured_contexts.append(context)
                return AgentResponse(run_id="run-3", answer="ok", status="completed")

        verified_context = PermissionContext(
            user_id="query-user",
            username="test2",
            roles=["Gamma"],
            allowed_tools=["list_dashboards"],
            mcp_bearer_token="query-token",
        )

        with patch(
            "superset_agent_service.agents.api.AgentService",
            CapturingAgentService,
        ), patch(
            "superset_agent_service.agents.api.settings.SUPERSET_AGENT_TOKEN_VERIFY_URL",
            "http://superset.local/api/v1/agent/token/verify",
        ), patch(
            "superset_agent_service.agents.api.token_verifier.verify",
            new=AsyncMock(return_value=verified_context),
        ) as verify:
            with TestClient(app) as client:
                with client.websocket_connect(
                    "/api/v1/agents/ws?agent_token=query-token"
                ) as socket:
                    self.assertEqual(socket.receive_json(), {"type": "connected"})
                    self.assertEqual(socket.receive_json(), {"type": "authenticated"})
                    socket.send_json(
                        {
                            "type": "run",
                            "request": {
                                "question": "list dashboards",
                                "filters": {},
                            },
                        }
                    )

                    final = socket.receive_json()
                    self.assertEqual(final["type"], "final")

        verify.assert_awaited_once_with("query-token")
        self.assertEqual(captured_contexts[0].user_id, "query-user")
        self.assertEqual(captured_contexts[0].mcp_bearer_token, "query-token")

    def test_socket_ignores_query_token_when_production_switch_is_disabled(self):
        """Require message-body authentication when URL tokens are disabled.

        生产环境关闭 URL Token 后，只允许使用 WebSocket 消息体中的 Token 认证。
        """

        verified_context = PermissionContext(
            user_id="message-user",
            roles=["Admin"],
            mcp_bearer_token="message-token",
        )

        with patch(
            "superset_agent_service.agents.api.AgentService",
            FakeStreamingAgentService,
        ), patch(
            "superset_agent_service.agents.api.settings.SUPERSET_AGENT_TOKEN_VERIFY_URL",
            "http://superset.local/api/v1/agent/token/verify",
        ), patch(
            "superset_agent_service.agents.api.settings.ALLOW_WEBSOCKET_QUERY_TOKEN",
            False,
        ), patch(
            "superset_agent_service.agents.api.token_verifier.verify",
            new=AsyncMock(return_value=verified_context),
        ) as verify:
            with TestClient(app) as client:
                with client.websocket_connect(
                    "/api/v1/agents/ws?agent_token=ignored-query-token"
                ) as socket:
                    self.assertEqual(socket.receive_json(), {"type": "connected"})
                    socket.send_json(
                        {
                            "type": "run",
                            "token": "message-token",
                            "request": {
                                "question": "list dashboards",
                                "filters": {},
                            },
                        }
                    )
                    while True:
                        message = socket.receive_json()
                        if message["type"] == "final":
                            break

        verify.assert_awaited_once_with("message-token")


if __name__ == "__main__":
    unittest.main()
