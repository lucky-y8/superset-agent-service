"""SQLAlchemy models for durable Agent audit logs.

用于持久化 Agent 审计日志的 SQLAlchemy 模型。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from superset_agent_service.db.base import Base
from superset_agent_service.runs.models import utc_now


class AgentAuditLogModel(Base):
    """Persist one security or compliance audit event.

    持久化一条安全或合规审计事件。
    """

    __tablename__ = "agent_audit_logs"
    __table_args__ = (
        Index("ix_agent_audit_logs_run_id_created_at", "run_id", "created_at"),
        Index("ix_agent_audit_logs_user_action", "user_id", "action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
