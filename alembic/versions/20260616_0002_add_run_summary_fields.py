"""Add Agent run summary fields.

Revision ID: 20260616_0002
Revises: 20260611_0001
Create Date: 2026-06-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260616_0002"
down_revision: str | None = "20260611_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add durable answer, timing, token, and error summary columns.

    增加用于持久化答案、耗时、Token 和错误摘要的列。
    """

    op.add_column("agent_runs", sa.Column("question", sa.Text(), nullable=True))
    op.add_column("agent_runs", sa.Column("final_answer", sa.Text(), nullable=True))
    op.add_column("agent_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("agent_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("total_tokens", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("cost_usd", sa.Float(), nullable=True))
    op.execute("UPDATE agent_runs SET started_at = created_at WHERE started_at IS NULL")


def downgrade() -> None:
    """Remove Agent run summary columns.

    删除 Agent 运行摘要相关字段。
    """

    op.drop_column("agent_runs", "cost_usd")
    op.drop_column("agent_runs", "total_tokens")
    op.drop_column("agent_runs", "output_tokens")
    op.drop_column("agent_runs", "input_tokens")
    op.drop_column("agent_runs", "duration_ms")
    op.drop_column("agent_runs", "completed_at")
    op.drop_column("agent_runs", "started_at")
    op.drop_column("agent_runs", "error_message")
    op.drop_column("agent_runs", "final_answer")
    op.drop_column("agent_runs", "question")
