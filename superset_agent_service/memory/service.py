"""Application service for durable Agent long-term memory.

Agent 长期记忆的应用服务。
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.db.session import AsyncSessionLocal
from superset_agent_service.memory.models import AgentMemoryModel
from superset_agent_service.memory.schemas import AgentMemory, MemoryUpsertRequest

SessionFactory = async_sessionmaker[AsyncSession]


class MemoryService:
    """Read and write user-scoped long-term memories.

    读取和写入按用户隔离的长期记忆。
    """

    def __init__(self, session_factory: SessionFactory = AsyncSessionLocal) -> None:
        """Create a memory service with a replaceable session factory.

        创建一个会话工厂可替换的记忆服务。
        """

        self.session_factory = session_factory

    async def upsert_memory(
        self,
        *,
        context: PermissionContext,
        memory_type: str,
        memory_key: str,
        memory_value: dict[str, Any],
        source: str | None = None,
        confidence: float = 1.0,
        description: str | None = None,
        expires_at: datetime | None = None,
    ) -> AgentMemory:
        """Create or update one scoped memory item.

        创建或更新一条带作用域的记忆。
        """

        tenant_id = context.tenant_id or ""
        now = _utc_now()
        async with self.session_factory() as session:
            existing = await session.scalar(
                select(AgentMemoryModel).where(
                    AgentMemoryModel.user_id == context.user_id,
                    AgentMemoryModel.tenant_id == tenant_id,
                    AgentMemoryModel.memory_type == memory_type,
                    AgentMemoryModel.memory_key == memory_key,
                )
            )
            if existing is None:
                existing = AgentMemoryModel(
                    memory_id=str(uuid4()),
                    user_id=context.user_id,
                    tenant_id=tenant_id,
                    memory_type=memory_type,
                    memory_key=memory_key,
                    memory_value=memory_value,
                    source=source,
                    confidence=confidence,
                    description=description,
                    expires_at=expires_at,
                    last_used_at=now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(existing)
            else:
                existing.memory_value = memory_value
                existing.source = source
                existing.confidence = confidence
                existing.description = description
                existing.expires_at = expires_at
                existing.last_used_at = now
                existing.updated_at = now
            await session.commit()
            await session.refresh(existing)
            return _to_schema(existing)

    async def upsert_from_request(
        self,
        *,
        context: PermissionContext,
        request: MemoryUpsertRequest,
    ) -> AgentMemory:
        """Create or update a memory item from an API request.

        根据 API 请求创建或更新一条记忆。
        """

        return await self.upsert_memory(
            context=context,
            memory_type=request.memory_type,
            memory_key=request.memory_key,
            memory_value=request.memory_value,
            source=request.source,
            confidence=request.confidence,
            description=request.description,
            expires_at=request.expires_at,
        )

    async def list_memories(
        self,
        *,
        context: PermissionContext,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[AgentMemory]:
        """List non-expired memories visible to the current user.

        列出当前用户可见且未过期的记忆。
        """

        now = _utc_now()
        filters = [
            AgentMemoryModel.user_id == context.user_id,
            AgentMemoryModel.tenant_id == (context.tenant_id or ""),
            or_(
                AgentMemoryModel.expires_at.is_(None),
                AgentMemoryModel.expires_at > now,
            ),
        ]
        if memory_type:
            filters.append(AgentMemoryModel.memory_type == memory_type)
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(AgentMemoryModel)
                .where(and_(*filters))
                .order_by(AgentMemoryModel.last_used_at.desc())
                .limit(limit)
            )
            memories = list(rows)
            for memory in memories:
                memory.last_used_at = now
            await session.commit()
            return [_to_schema(memory) for memory in memories]

    async def delete_memory(
        self,
        *,
        context: PermissionContext,
        memory_id: str,
    ) -> bool:
        """Delete one memory owned by the current user.

        删除当前用户拥有的一条记忆。
        """

        async with self.session_factory() as session:
            result = await session.execute(
                delete(AgentMemoryModel).where(
                    AgentMemoryModel.memory_id == memory_id,
                    AgentMemoryModel.user_id == context.user_id,
                    AgentMemoryModel.tenant_id == (context.tenant_id or ""),
                )
            )
            await session.commit()
            return bool(result.rowcount)

    async def get_runtime_context(
        self,
        *,
        context: PermissionContext,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return compact memories that can be safely placed in the prompt.

        返回可以安全放入 Prompt 的紧凑记忆上下文。
        """

        memories = await self.list_memories(context=context, limit=limit)
        resources: dict[str, Any] = {}
        recent_tool_results: list[dict[str, Any]] = []
        preferences: dict[str, Any] = {}
        facts: list[dict[str, Any]] = []

        for memory in memories:
            if memory.memory_type == "resource_ref":
                resources[memory.memory_key] = memory.memory_value
            elif memory.memory_type == "recent_tool_result":
                recent_tool_results.append(
                    {
                        "tool": memory.memory_key,
                        "value": memory.memory_value,
                        "last_used_at": memory.last_used_at.isoformat(),
                    }
                )
            elif memory.memory_type == "preference":
                preferences[memory.memory_key] = memory.memory_value
            else:
                facts.append(
                    {
                        "type": memory.memory_type,
                        "key": memory.memory_key,
                        "value": memory.memory_value,
                    }
                )

        return {
            "resources": resources,
            "preferences": preferences,
            "recent_tool_results": recent_tool_results[:5],
            "facts": facts[:10],
        }

    async def remember_tool_result(
        self,
        *,
        context: PermissionContext,
        tool_name: str,
        result: Any,
    ) -> list[AgentMemory]:
        """Extract useful resource references from a tool result.

        从工具结果中抽取有用的资源引用并写入长期记忆。
        """

        parsed = _normalize_tool_result(result)
        writes: list[AgentMemory] = []
        for key, value in _extract_resource_refs(tool_name, parsed).items():
            writes.append(
                await self.upsert_memory(
                    context=context,
                    memory_type="resource_ref",
                    memory_key=key,
                    memory_value=value,
                    source=f"tool:{tool_name}",
                    confidence=0.9,
                    description=f"Last {key} observed from {tool_name}.",
                )
            )

        writes.append(
            await self.upsert_memory(
                context=context,
                memory_type="recent_tool_result",
                memory_key=tool_name,
                memory_value={"summary": _safe_summary(parsed)},
                source=f"tool:{tool_name}",
                confidence=0.7,
                description="Recent tool result summary for conversational recall.",
            )
        )
        return writes


def _normalize_tool_result(result: Any) -> Any:
    """Parse common MCP text-wrapped JSON results.

    解析 MCP 常见的文本包裹 JSON 结果。
    """

    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            parsed_parts: list[Any] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parsed_parts.append(_maybe_json(item["text"]))
                else:
                    parsed_parts.append(item)
            if len(parsed_parts) == 1:
                return parsed_parts[0]
            return parsed_parts
    return result


def _maybe_json(text: str) -> Any:
    """Return parsed JSON when text contains JSON, otherwise return the text.

    当文本内容是 JSON 时返回解析结果，否则返回原文本。
    """

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _extract_resource_refs(tool_name: str, value: Any) -> dict[str, dict[str, Any]]:
    """Extract known Superset resource IDs from arbitrary tool results.

    从任意工具结果中抽取已知 Superset 资源 ID。
    """

    refs: dict[str, dict[str, Any]] = {}
    lower_tool = tool_name.lower()
    for item in _walk_objects(value):
        normalized = {str(key).lower(): str(key) for key in item}
        if "dataset_id" in normalized:
            _put_ref(refs, "last_dataset", item, normalized["dataset_id"])
        if "datasource_id" in normalized and "dataset" in lower_tool:
            _put_ref(refs, "last_dataset", item, normalized["datasource_id"])
        if "chart_id" in normalized:
            _put_ref(refs, "last_chart", item, normalized["chart_id"])
        if "slice_id" in normalized:
            _put_ref(refs, "last_chart", item, normalized["slice_id"])
        if "dashboard_id" in normalized:
            _put_ref(refs, "last_dashboard", item, normalized["dashboard_id"])

        if "id" in normalized:
            if "dataset" in lower_tool and "last_dataset" not in refs:
                _put_ref(refs, "last_dataset", item, normalized["id"])
            elif "chart" in lower_tool and "last_chart" not in refs:
                _put_ref(refs, "last_chart", item, normalized["id"])
            elif "dashboard" in lower_tool and "last_dashboard" not in refs:
                _put_ref(refs, "last_dashboard", item, normalized["id"])
    return refs


def _put_ref(
    refs: dict[str, dict[str, Any]],
    key: str,
    item: dict[str, Any],
    id_key: str,
) -> None:
    """Store one resource reference if the source object has a usable ID.

    当来源对象包含可用 ID 时保存一条资源引用。
    """

    resource_id = item.get(id_key)
    if resource_id in (None, ""):
        return
    refs[key] = {
        "id": str(resource_id),
        "title": _first_present(
            item,
            "name",
            "title",
            "dashboard_title",
            "slice_name",
            "table_name",
            "dataset_name",
        ),
        "raw": _compact_mapping(item),
    }


def _walk_objects(value: Any) -> list[dict[str, Any]]:
    """Return dictionaries found inside nested lists and dictionaries.

    返回嵌套列表和字典中的所有字典对象。
    """

    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for nested in value.values():
            found.extend(_walk_objects(nested))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_objects(item))
    return found


def _first_present(item: dict[str, Any], *keys: str) -> str | None:
    """Return the first non-empty string-like value for candidate keys.

    返回候选字段中第一个非空、类似字符串的值。
    """

    lowered = {str(key).lower(): value for key, value in item.items()}
    for key in keys:
        value = lowered.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _compact_mapping(item: dict[str, Any]) -> dict[str, Any]:
    """Keep a small resource snapshot instead of huge tool results.

    只保留小型资源快照，避免把大型工具结果完整写入记忆。
    """

    allowed = {
        "id",
        "dataset_id",
        "datasource_id",
        "chart_id",
        "slice_id",
        "dashboard_id",
        "name",
        "title",
        "dashboard_title",
        "slice_name",
        "table_name",
        "dataset_name",
        "published",
        "url",
        "slug",
    }
    return {
        str(key): value
        for key, value in item.items()
        if str(key).lower() in allowed
    }


def _safe_summary(value: Any, max_length: int = 2000) -> str:
    """Serialize a bounded summary for memory storage.

    序列化一段有长度上限的摘要用于记忆存储。
    """

    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}...<truncated>"


def _to_schema(model: AgentMemoryModel) -> AgentMemory:
    """Convert an ORM memory row into an API schema.

    将 ORM 记忆行转换为 API 数据结构。
    """

    return AgentMemory(
        memory_id=model.memory_id,
        user_id=model.user_id,
        tenant_id=model.tenant_id or None,
        memory_type=model.memory_type,
        memory_key=model.memory_key,
        memory_value=model.memory_value,
        source=model.source,
        confidence=model.confidence,
        description=model.description,
        expires_at=model.expires_at,
        last_used_at=model.last_used_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp.

    返回当前带 UTC 时区信息的时间戳。
    """

    return datetime.now(UTC)
