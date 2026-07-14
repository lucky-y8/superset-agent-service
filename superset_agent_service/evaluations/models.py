"""Database models for deterministic Agent evaluations.

用于确定性 Agent 自动评估的数据库模型。
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from superset_agent_service.db.base import Base
from superset_agent_service.runs.models import utc_now


class EvaluationCaseModel(Base):
    """Store one reusable question and its machine-checkable expectations.

    保存一个可重复执行的问题及其机器可判定的期望结果。
    """

    __tablename__ = "agent_evaluation_cases"

    case_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_tools: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expected_answer_contains: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    forbidden_answer_contains: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    request_context: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    minimum_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class EvaluationResultModel(Base):
    """Persist the reproducible score of one case against one Agent run.

    持久化一个评估用例针对一次 Agent 运行得到的可复现评分。
    """

    __tablename__ = "agent_evaluation_results"
    __table_args__ = (
        Index("ix_agent_evaluation_results_case_time", "case_id", "evaluated_at"),
        Index("ix_agent_evaluation_results_run_id", "run_id"),
    )

    result_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    case_id: Mapped[str] = mapped_column(
        ForeignKey("agent_evaluation_cases.case_id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    answer_score: Mapped[float] = mapped_column(Float, nullable=False)
    tool_score: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evaluated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
