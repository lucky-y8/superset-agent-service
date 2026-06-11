"""WebSocket protocol tests for live Agent progress events.

Agent 实时进度事件的 WebSocket 协议测试。
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from superset_agent_service.agents.schemas import AgentResponse
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


if __name__ == "__main__":
    unittest.main()
