"""Pydantic schemas for the knowledge-base RAG API.

知识库 RAG API 使用的 Pydantic 数据结构。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    """Expose one uploaded knowledge document to API callers.

    向 API 调用方展示一个已经上传的知识文档。
    """

    document_id: str
    filename: str
    content_type: str | None = None
    status: str
    owner_user_id: str
    access_scope: str
    chunk_count: int = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeUploadResponse(BaseModel):
    """Return the result of one knowledge upload and indexing request.

    返回一次知识上传与索引请求的处理结果。
    """

    document: KnowledgeDocument
    message: str


class KnowledgeSearchRequest(BaseModel):
    """Describe a semantic search request over the knowledge base.

    描述一次面向知识库的语义检索请求。
    """

    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    """Return one permission-filtered knowledge search hit.

    返回一条已经过权限过滤的知识检索结果。
    """

    document_id: str
    chunk_id: str
    filename: str
    text: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    """Return semantic search results for one query.

    返回一次语义检索的结果集合。
    """

    results: list[KnowledgeSearchResult]
