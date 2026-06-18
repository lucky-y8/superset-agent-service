"""Streamable HTTP client for communicating with an MCP server.

用于和 MCP 服务通信的 Streamable HTTP 客户端。

MCP uses JSON-RPC 2.0 messages, but an HTTP MCP server may return those
messages either as normal JSON or as Server-Sent Events (SSE).  Keeping the
transport details in this module prevents Agent workflows and API handlers
from having to understand HTTP headers, SSE framing, or JSON-RPC errors.

MCP 使用 JSON-RPC 2.0 消息，但 HTTP MCP 服务既可能返回普通 JSON，也可能
返回服务器发送事件（SSE）。把传输细节集中在本模块中，可以避免 Agent 工作流
和 API 处理器理解 HTTP 请求头、SSE 分帧或 JSON-RPC 错误。
"""

import asyncio
import json
import logging
from itertools import count
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class MCPError(RuntimeError):
    """Raised when the MCP server returns a JSON-RPC protocol error.

    MCP 服务返回 JSON-RPC 协议错误时抛出。
    """


class MCPTransportError(RuntimeError):
    """Raised when HTTP transport fails before MCP can return a result.

    MCP 返回结果前 HTTP 传输失败时抛出。
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Preserve a readable message and optional upstream HTTP status.

        保存可读错误信息和可选的上游 HTTP 状态码。
        """

        super().__init__(message)
        self.status_code = status_code


class MCPClient:
    """Small asynchronous client for the MCP Streamable HTTP transport.

    面向 MCP Streamable HTTP 传输的轻量异步客户端。
    """

    def __init__(
        self,
        base_url: str,
        bearer_token: str | None = None,
        timeout_seconds: float = 60,
    ) -> None:
        """Store endpoint credentials and create monotonically increasing IDs.

        保存端点凭据，并创建持续递增的请求 ID。
        """

        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.timeout_seconds = timeout_seconds
        self._request_ids = count(1)

    async def initialize(self) -> dict[str, Any]:
        """Negotiate the MCP protocol and return server capabilities.

        协商 MCP 协议并返回服务能力。

        Calling ``initialize`` is also a useful connectivity check because it
        verifies much more than an open TCP port: the endpoint must understand
        MCP JSON-RPC and return a valid initialization result.

        调用 ``initialize`` 也能作为有效的连通性检查，因为它验证的不只是 TCP
        端口可用，还要求端点理解 MCP JSON-RPC 并返回合法初始化结果。
        """

        return await self._request(
            method="initialize",
            params={
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {
                    "name": "superset-agent-service",
                    "version": "0.1.0",
                },
            },
        )

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the tools visible to the current MCP identity.

        返回当前 MCP 身份能够看到的工具。

        MCP servers commonly filter this list by the authenticated user's
        permissions.  Therefore an empty list means "connected, but no tools
        are visible" rather than automatically meaning the server is down.

        MCP 服务通常会依据已认证用户的权限过滤此列表。因此空列表表示“已连接，
        但当前没有可见工具”，不能直接判断为服务离线。
        """

        result = await self._request(method="tools/list", params={})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise MCPError("MCP tools/list returned a non-list 'tools' value")
        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, object]
    ) -> Any:
        """Call one MCP tool using its exact schema-defined arguments.

        使用工具 Schema 定义的精确参数调用一个 MCP 工具。
        """

        return await self._request(
            method="tools/call",
            params={"name": name, "arguments": arguments},
            require_object_result=False,
        )

    async def _request(
        self,
        method: str,
        params: dict[str, object],
        require_object_result: bool = True,
    ) -> Any:
        """Send one JSON-RPC request and return its JSON-RPC ``result``.

        发送一条 JSON-RPC 请求，并返回其中的 ``result``。

        MCP control methods such as ``initialize`` and ``tools/list`` return
        objects.  Tool execution is more flexible: a server may return an
        object, array, string, number, boolean, or null.  The caller therefore
        opts out of the object-only validation for ``tools/call``.

        ``initialize`` 和 ``tools/list`` 等控制方法返回对象；工具执行更加灵活，
        可以返回对象、数组、字符串、数字、布尔值或 null。因此 ``tools/call``
        会关闭“结果必须为对象”的校验。
        """

        payload = {
            "jsonrpc": "2.0",
            "id": next(self._request_ids),
            "method": method,
            "params": params,
        }
        headers = {
            # Streamable HTTP servers are allowed to choose JSON or SSE.
            # Streamable HTTP 服务可以自行选择返回 JSON 或 SSE。
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        logger.info(
            "MCP request: url=%s method=%s params=%s has_bearer_token=%s",
            self.base_url,
            method,
            self._summarize_for_log(params),
            bool(self.bearer_token),
        )

        # urllib is synchronous, so it runs in a worker thread.  The public
        # client remains async and will not block FastAPI's event loop while it
        # waits for the MCP server.
        # urllib 是同步库，因此放入工作线程运行。这样公开客户端仍保持异步，
        # 等待 MCP 服务时也不会阻塞 FastAPI 的事件循环。
        content_type, body = await asyncio.to_thread(
            self._post_json,
            headers,
            payload,
        )
        message = self._parse_response(content_type, body)
        if "error" in message:
            error = message["error"]
            logger.warning(
                "MCP JSON-RPC error: method=%s error=%s",
                method,
                self._summarize_for_log(error),
            )
            if isinstance(error, dict):
                code = error.get("code", "unknown")
                detail = error.get("message", "Unknown MCP error")
                raise MCPError(f"MCP error {code}: {detail}")
            raise MCPError(f"MCP returned an invalid error object: {error!r}")

        result = message.get("result")
        if require_object_result and not isinstance(result, dict):
            raise MCPError("MCP response does not contain an object result")
        logger.info(
            "MCP response: method=%s result=%s",
            method,
            self._summarize_for_log(result),
        )
        return result

    def _post_json(
        self,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> tuple[str, str]:
        """Perform the blocking HTTP request used by the async wrapper.

        执行异步包装器内部使用的阻塞 HTTP 请求。
        """

        request = Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = response.headers.get("content-type", "")
                body = response.read().decode("utf-8")
                logger.info(
                    "MCP HTTP response: status=%s content_type=%s body_length=%s",
                    response.status,
                    content_type,
                    len(body),
                )
                return content_type, body
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            logger.warning(
                "MCP HTTP error: status=%s body=%s",
                exc.code,
                self._truncate(error_body),
            )
            raise MCPTransportError(
                f"MCP server returned HTTP {exc.code}",
                status_code=exc.code,
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise MCPTransportError(f"Cannot connect to MCP server: {exc}") from exc

    def _summarize_for_log(self, value: Any, max_length: int = 1200) -> str:
        """Serialize and truncate MCP payloads before logging.

        日志打印 MCP 请求和响应前先序列化并截断，避免输出过大。
        """

        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
        return self._truncate(text, max_length=max_length)

    def _truncate(self, text: str, max_length: int = 1200) -> str:
        """Return a bounded log string.

        返回长度受控的日志字符串。
        """

        if len(text) <= max_length:
            return text
        return f"{text[:max_length]}...<truncated>"

    @staticmethod
    def _parse_response(content_type: str, body: str) -> dict[str, Any]:
        """Decode either an application/json or text/event-stream response.

        解码 application/json 或 text/event-stream 响应。
        """

        content_type = content_type.lower()
        if "text/event-stream" not in content_type:
            message = json.loads(body)
            if not isinstance(message, dict):
                raise MCPError("MCP JSON response must be an object")
            return message

        # A tool may emit logging/progress notifications before its final
        # JSON-RPC response.  Each SSE event can also contain several ``data:``
        # lines, so events must be parsed independently and notifications
        # skipped until a message with ``result`` or ``error`` is found.
        # 工具在最终 JSON-RPC 响应前可能发送日志或进度通知。每个 SSE 事件还可能
        # 包含多行 ``data:``，因此必须逐事件解析，并跳过通知，直到找到带有
        # ``result`` 或 ``error`` 的消息。
        data_lines: list[str] = []
        for line in body.splitlines():
            if line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").lstrip())
            elif not line.strip() and data_lines:
                message = json.loads("\n".join(data_lines))
                if (
                    isinstance(message, dict)
                    and ("result" in message or "error" in message)
                ):
                    return message
                data_lines = []

        # Handle a final event even when the server omits the trailing blank
        # line.  This is legal in practice and common in hand-written fixtures.
        # 即使服务省略了结尾空行，也要处理最后一个事件。这种情况在实践中可用，
        # 也常见于手写测试数据。
        if data_lines:
            message = json.loads("\n".join(data_lines))
            if (
                isinstance(message, dict)
                and ("result" in message or "error" in message)
            ):
                return message

        raise MCPError("MCP SSE response did not contain a JSON-RPC result event")
