"""Create automatic evaluation case and result tables.

Revision ID: 20260713_0006
Revises: 20260629_0005
Create Date: 2026-07-13

创建自动评估用例表和评估结果表。
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260713_0006"
down_revision: str | None = "20260629_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create reusable quality baselines and their scored results.

    创建可复用的质量基线及其评分结果表。
    """

    op.create_table(
        "agent_evaluation_cases",
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_tools", sa.JSON(), nullable=False),
        sa.Column("expected_answer_contains", sa.JSON(), nullable=False),
        sa.Column("forbidden_answer_contains", sa.JSON(), nullable=False),
        sa.Column("request_context", sa.JSON(), nullable=False),
        sa.Column("minimum_score", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("case_id"),
    )
    op.create_table(
        "agent_evaluation_results",
        sa.Column("result_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("answer_score", sa.Float(), nullable=False),
        sa.Column("tool_score", sa.Float(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("evaluated_by", sa.String(length=255), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["agent_evaluation_cases.case_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("result_id"),
    )
    op.create_index(
        "ix_agent_evaluation_results_case_time",
        "agent_evaluation_results",
        ["case_id", "evaluated_at"],
    )
    op.create_index(
        "ix_agent_evaluation_results_run_id",
        "agent_evaluation_results",
        ["run_id"],
    )
    op.create_index(
        "ix_agent_evaluation_results_status",
        "agent_evaluation_results",
        ["status"],
    )


def downgrade() -> None:
    """Remove evaluation results before their parent cases.

    先删除评估结果，再删除其父级评估用例。
    """

    op.drop_index(
        "ix_agent_evaluation_results_status", table_name="agent_evaluation_results"
    )
    op.drop_index(
        "ix_agent_evaluation_results_run_id", table_name="agent_evaluation_results"
    )
    op.drop_index(
        "ix_agent_evaluation_results_case_time",
        table_name="agent_evaluation_results",
    )
    op.drop_table("agent_evaluation_results")
    op.drop_table("agent_evaluation_cases")
