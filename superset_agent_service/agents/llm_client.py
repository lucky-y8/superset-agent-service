"""OpenAI-compatible chat client used by the Agent Runtime.

Agent Runtime 使用的 OpenAI 兼容聊天客户端。

DeepSeek deliberately implements the OpenAI chat-completions protocol, so the
Runtime only needs a small HTTP client rather than a provider-specific SDK.
Keeping this adapter local also makes every request and response shape visible
to developers who are learning how tool calling works.

DeepSeek 实现了 OpenAI Chat Completions 协议，因此 Runtime 只需要一个轻量
HTTP 客户端，无需依赖特定厂商的 SDK。将适配器保留在项目内部，也便于学习者
直接观察工具调用时每个请求和响应的数据结构。
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx


class LLMConfigurationError(RuntimeError):
    """Raised when the model cannot start because configuration is incomplete.

    模型因配置不完整而无法启动时抛出。
    """


class LLMResponseError(RuntimeError):
    """Raised when the provider returns an HTTP or response-format error.

    模型服务返回 HTTP 错误或响应格式错误时抛出。
    """


class OpenAICompatibleChatClient:
    """Send chat-completion requests to DeepSeek or another compatible API.

    向 DeepSeek 或其他兼容接口发送聊天补全请求。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 60,
    ) -> None:
        """Store connection settings without opening a network connection.

        保存连接配置，此时不会立即建立网络连接。
        """

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        on_content_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """Return the first assistant message from one model response.

        返回一次模型响应中的第一条 assistant 消息。

        The assistant message can contain normal ``content``, one or more
        ``tool_calls``, or both.  The Runtime owns the loop because only it
        knows how to execute MCP tools and append their results.

        assistant 消息可以包含普通 ``content``、一个或多个 ``tool_calls``，
        也可以两者同时存在。工具循环由 Runtime 管理，因为只有它知道如何执行
        MCP 工具并把结果追加回对话。
        """

        if not self.api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is not configured; add it to the local .env file"
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            # A low temperature is a better default for analytics tasks where
            # deterministic tool selection matters more than creative prose.
            # 分析类任务更重视稳定的工具选择，因此低温度比创意表达更合适。
            "temperature": 0.1,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if on_content_delta is not None:
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}
            return await self._complete_stream(payload, on_content_delta)

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Do not include request headers in this error because they contain
            # the API key.  A short response body is enough for local diagnosis.
            # 请求头包含 API Key，因此错误信息中不能输出请求头；截取响应正文即可排查。
            detail = exc.response.text[:1000]
            raise LLMResponseError(
                f"Model API returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMResponseError(f"Cannot connect to model API: {exc}") from exc

        data = response.json()
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMResponseError("Model response does not contain any choices")

        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise LLMResponseError("Model response does not contain an assistant message")
        usage = data.get("usage")
        if isinstance(usage, dict):
            message["_usage"] = usage
        return message

    async def _complete_stream(
        self,
        payload: dict[str, Any],
        on_content_delta: Callable[[str], Awaitable[None]],
    ) -> dict[str, Any]:
        """Assemble a streamed assistant message while forwarding text tokens.

        在转发文本 Token 的同时，组装完整的流式 assistant 消息。

        DeepSeek streams both normal content and fragmented tool calls. Tool
        names and JSON arguments are reconstructed by their array index so the
        final message has the same shape as a non-streaming response.

        DeepSeek 会流式返回普通内容和被拆分的工具调用。这里按照数组索引重建工具名
        与 JSON 参数，使最终消息结构与非流式响应保持一致。
        """

        content_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        usage: dict[str, Any] | None = None

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if not data or data == "[DONE]":
                            continue

                        chunk = json.loads(data)
                        chunk_usage = chunk.get("usage")
                        if isinstance(chunk_usage, dict):
                            usage = chunk_usage
                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        if not isinstance(delta, dict):
                            continue

                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            content_parts.append(content)
                            await on_content_delta(content)

                        for fragment in delta.get("tool_calls", []) or []:
                            if not isinstance(fragment, dict):
                                continue
                            index = int(fragment.get("index", 0))
                            assembled = tool_calls.setdefault(
                                index,
                                {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                },
                            )
                            if fragment.get("id"):
                                assembled["id"] = fragment["id"]
                            function = fragment.get("function", {})
                            if isinstance(function, dict):
                                if function.get("name"):
                                    assembled["function"]["name"] += function["name"]
                                if function.get("arguments"):
                                    assembled["function"]["arguments"] += function[
                                        "arguments"
                                    ]
        except httpx.HTTPStatusError as exc:
            detail = (await exc.response.aread()).decode("utf-8", errors="replace")[
                :1000
            ]
            raise LLMResponseError(
                f"Model API returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise LLMResponseError(f"Model streaming request failed: {exc}") from exc

        message: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(content_parts) or None,
        }
        if tool_calls:
            message["tool_calls"] = [
                tool_calls[index] for index in sorted(tool_calls)
            ]
        if usage is not None:
            message["_usage"] = usage
        return message
