"""SQLAlchemy models for durable Agent run traces.

用于持久化 Agent 运行轨迹的 SQLAlchemy 模型。
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from superset_agent_service.db.base import Base


def utc_now() -> datetime:
    """Return an aware UTC timestamp for database defaults.

    返回带 UTC 时区信息的时间戳，作为数据库字段默认值。
    """

    return datetime.now(UTC)


class AgentRunModel(Base):
    """Persist the identity and current lifecycle status of one Agent run.

    持久化一次 Agent 运行的身份信息和当前生命周期状态。
    """

    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="created",
        index=True,
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
    events: Mapped[list["AgentRunEventModel"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentRunEventModel.id",
    )


class AgentRunEventModel(Base):
    """Persist one ordered event belonging to an Agent run.

    持久化一条属于某次 Agent 运行的有序事件。
    """

    __tablename__ = "agent_run_events"
    __table_args__ = (
        Index("ix_agent_run_events_run_id_id", "run_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    run: Mapped[AgentRunModel] = relationship(back_populates="events")
