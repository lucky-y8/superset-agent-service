"""SQLAlchemy models for durable Agent long-term memory.

Agent 长期记忆使用的 SQLAlchemy 持久化模型。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from superset_agent_service.db.base import Base
from superset_agent_service.runs.models import utc_now


class AgentMemoryModel(Base):
    """Persist one scoped memory item for one user.

    为某个用户持久化一条带作用域的记忆。
    """

    __tablename__ = "agent_memories"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "tenant_id",
            "memory_type",
            "memory_key",
            name="uq_agent_memories_scope_key",
        ),
        Index("ix_agent_memories_user_type", "user_id", "memory_type"),
        Index("ix_agent_memories_last_used", "user_id", "last_used_at"),
    )

    memory_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    memory_key: Mapped[str] = mapped_column(String(255), nullable=False)
    memory_value: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
