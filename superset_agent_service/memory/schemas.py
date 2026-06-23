"""Pydantic schemas for Agent long-term memory APIs.

Agent 长期记忆 API 使用的 Pydantic 数据结构。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentMemory(BaseModel):
    """Expose one long-term memory item.

    对外展示一条长期记忆。
    """

    memory_id: str
    user_id: str
    tenant_id: str | None = None
    memory_type: str
    memory_key: str
    memory_value: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    confidence: float = 1.0
    description: str | None = None
    expires_at: datetime | None = None
    last_used_at: datetime
    created_at: datetime
    updated_at: datetime


class MemoryUpsertRequest(BaseModel):
    """Describe one manual memory upsert request.

    描述一次手动写入或更新记忆的请求。
    """

    memory_type: str = Field(min_length=1, max_length=64)
    memory_key: str = Field(min_length=1, max_length=255)
    memory_value: dict[str, Any] = Field(default_factory=dict)
    source: str | None = "manual"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    description: str | None = None
    expires_at: datetime | None = None


class MemoryListResponse(BaseModel):
    """Return the current user's memory items.

    返回当前用户的记忆条目。
    """

    memories: list[AgentMemory]
