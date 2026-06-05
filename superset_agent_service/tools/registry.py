"""Tool registry primitives for controlled agent tool execution."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


ToolHandler = Callable[[dict[str, object]], Awaitable[dict[str, object]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: ToolHandler
    permission: str = "agent:use"
    timeout_seconds: int = 30


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    @classmethod
    def default(cls) -> "ToolRegistry":
        registry = cls()
        return registry

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        return self._tools[name]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())
