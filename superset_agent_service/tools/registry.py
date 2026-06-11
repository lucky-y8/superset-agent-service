"""Tool registry primitives for controlled agent tool execution.

用于受控执行 Agent 工具的注册表基础结构。
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


ToolHandler = Callable[[dict[str, object]], Awaitable[dict[str, object]]]


@dataclass(frozen=True)
class ToolDefinition:
    """Describe an executable tool and its operational restrictions.

    描述一个可执行工具及其运行限制。
    """

    name: str
    description: str
    handler: ToolHandler
    permission: str = "agent:use"
    timeout_seconds: int = 30


class ToolRegistry:
    """Store locally implemented tools by their unique names.

    按唯一名称保存本地实现的工具。
    """

    def __init__(self) -> None:
        """Create an empty local tool registry.

        创建一个空的本地工具注册表。
        """

        self._tools: dict[str, ToolDefinition] = {}

    @classmethod
    def default(cls) -> "ToolRegistry":
        """Build the default registry; MCP tools are discovered separately.

        构建默认注册表；MCP 工具由 Runtime 另行动态发现。
        """

        registry = cls()
        return registry

    def register(self, tool: ToolDefinition) -> None:
        """Register or replace one local tool by name.

        按名称注册或替换一个本地工具。
        """

        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        """Return one local tool by its exact name.

        按精确名称返回一个本地工具。
        """

        return self._tools[name]

    def list_tools(self) -> list[ToolDefinition]:
        """Return all local tool definitions.

        返回全部本地工具定义。
        """

        return list(self._tools.values())
