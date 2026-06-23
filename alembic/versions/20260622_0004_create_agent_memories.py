"""create agent memories

Revision ID: 20260622_0004
Revises: 20260622_0003
Create Date: 2026-06-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260622_0004"
down_revision = "20260622_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the durable long-term memory table.

    创建长期记忆持久化表。
    """

    op.create_table(
        "agent_memories",
        sa.Column("memory_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("memory_key", sa.String(length=255), nullable=False),
        sa.Column("memory_value", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("memory_id"),
        sa.UniqueConstraint(
            "user_id",
            "tenant_id",
            "memory_type",
            "memory_key",
            name="uq_agent_memories_scope_key",
        ),
    )
    op.create_index("ix_agent_memories_user_id", "agent_memories", ["user_id"])
    op.create_index(
        "ix_agent_memories_user_type",
        "agent_memories",
        ["user_id", "memory_type"],
    )
    op.create_index(
        "ix_agent_memories_last_used",
        "agent_memories",
        ["user_id", "last_used_at"],
    )


def downgrade() -> None:
    """Drop the durable long-term memory table.

    删除长期记忆持久化表。
    """

    op.drop_index("ix_agent_memories_last_used", table_name="agent_memories")
    op.drop_index("ix_agent_memories_user_type", table_name="agent_memories")
    op.drop_index("ix_agent_memories_user_id", table_name="agent_memories")
    op.drop_table("agent_memories")
