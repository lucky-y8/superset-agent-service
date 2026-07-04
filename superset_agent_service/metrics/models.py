"""SQLAlchemy models for durable Agent metrics.

用于持久化 Agent 指标数据的 SQLAlchemy 模型。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from superset_agent_service.db.base import Base
from superset_agent_service.runs.models import utc_now


class AgentMetricModel(Base):
    """Persist one model-call metric row for monitoring and cost analysis.

    持久化一条模型调用指标记录，用于监控、成本分析和故障排查。
    """

    __tablename__ = "agent_metrics"
    __table_args__ = (
        Index("ix_agent_metrics_run_id_created_at", "run_id", "created_at"),
        Index("ix_agent_metrics_provider_model", "provider", "model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="succeeded")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
