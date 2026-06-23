"""create rag knowledge tables

Revision ID: 20260622_0003
Revises: 20260616_0002
Create Date: 2026-06-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260622_0003"
down_revision = "20260616_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create durable metadata tables for RAG documents and chunks.

    为 RAG 文档和文本切片创建持久化元数据表。
    """

    op.create_table(
        "knowledge_documents",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("owner_user_id", sa.String(length=255), nullable=False),
        sa.Column("owner_username", sa.String(length=255), nullable=True),
        sa.Column("access_scope", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        "ix_knowledge_documents_owner_status",
        "knowledge_documents",
        ["owner_user_id", "status"],
    )
    op.create_index(
        "ix_knowledge_documents_owner_user_id",
        "knowledge_documents",
        ["owner_user_id"],
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.String(length=255), nullable=False),
        sa.Column("access_scope", sa.String(length=32), nullable=False),
        sa.Column("extra_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index(
        "ix_knowledge_chunks_document_id",
        "knowledge_chunks",
        ["document_id"],
    )
    op.create_index(
        "ix_knowledge_chunks_document_index",
        "knowledge_chunks",
        ["document_id", "chunk_index"],
    )
    op.create_index("ix_knowledge_chunks_owner", "knowledge_chunks", ["owner_user_id"])
    op.create_index(
        "ix_knowledge_chunks_owner_user_id",
        "knowledge_chunks",
        ["owner_user_id"],
    )


def downgrade() -> None:
    """Drop RAG knowledge metadata tables.

    删除 RAG 知识库元数据表。
    """

    op.drop_index("ix_knowledge_chunks_owner_user_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_owner", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_index", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index(
        "ix_knowledge_documents_owner_user_id",
        table_name="knowledge_documents",
    )
    op.drop_index(
        "ix_knowledge_documents_owner_status",
        table_name="knowledge_documents",
    )
    op.drop_table("knowledge_documents")
