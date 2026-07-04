"""create agent observability tables

Revision ID: 20260629_0005
Revises: 20260622_0004
Create Date: 2026-06-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260629_0005"
down_revision = "20260622_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create durable metrics and audit tables.

    创建持久化的指标表和审计表。
    """

    op.create_table(
        "agent_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.run_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_metrics_run_id", "agent_metrics", ["run_id"])
    op.create_index(
        "ix_agent_metrics_run_id_created_at",
        "agent_metrics",
        ["run_id", "created_at"],
    )
    op.create_index(
        "ix_agent_metrics_provider_model",
        "agent_metrics",
        ["provider", "model"],
    )

    op.create_table(
        "agent_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.run_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_audit_logs_run_id", "agent_audit_logs", ["run_id"])
    op.create_index("ix_agent_audit_logs_user_id", "agent_audit_logs", ["user_id"])
    op.create_index("ix_agent_audit_logs_action", "agent_audit_logs", ["action"])
    op.create_index(
        "ix_agent_audit_logs_run_id_created_at",
        "agent_audit_logs",
        ["run_id", "created_at"],
    )
    op.create_index(
        "ix_agent_audit_logs_user_action",
        "agent_audit_logs",
        ["user_id", "action"],
    )


def downgrade() -> None:
    """Drop durable metrics and audit tables.

    删除持久化的指标表和审计表。
    """

    op.drop_index("ix_agent_audit_logs_user_action", table_name="agent_audit_logs")
    op.drop_index(
        "ix_agent_audit_logs_run_id_created_at",
        table_name="agent_audit_logs",
    )
    op.drop_index("ix_agent_audit_logs_action", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_user_id", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_run_id", table_name="agent_audit_logs")
    op.drop_table("agent_audit_logs")

    op.drop_index("ix_agent_metrics_provider_model", table_name="agent_metrics")
    op.drop_index("ix_agent_metrics_run_id_created_at", table_name="agent_metrics")
    op.drop_index("ix_agent_metrics_run_id", table_name="agent_metrics")
    op.drop_table("agent_metrics")
