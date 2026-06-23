"""FastAPI routes for knowledge-base ingestion and retrieval.

知识库入库与检索的 FastAPI 路由。
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from superset_agent_service.auth.dependencies import get_permission_context
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.config import settings
from superset_agent_service.rag.schemas import (
    KnowledgeDocument,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeUploadResponse,
)
from superset_agent_service.rag.service import KnowledgeService

router = APIRouter()


@router.post(
    "/documents",
    response_model=KnowledgeUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    context: PermissionContext = Depends(get_permission_context),
) -> KnowledgeUploadResponse:
    """Upload a knowledge file and index it for the current user.

    上传知识文件，并为当前用户建立检索索引。
    """

    _ensure_rag_enabled()
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    service = KnowledgeService()
    document = await service.ingest_file(
        filename=file.filename or "upload.txt",
        content_type=file.content_type,
        data=data,
        context=context,
    )
    status_text = "indexed" if document.status == "indexed" else document.status
    return KnowledgeUploadResponse(
        document=document,
        message=f"Document {status_text} with {document.chunk_count} chunks.",
    )


@router.get("/documents", response_model=list[KnowledgeDocument])
async def list_documents(
    context: PermissionContext = Depends(get_permission_context),
) -> list[KnowledgeDocument]:
    """List knowledge documents owned by the current user.

    列出当前用户拥有的知识文档。
    """

    _ensure_rag_enabled()
    return await KnowledgeService().list_documents(context)


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    context: PermissionContext = Depends(get_permission_context),
) -> KnowledgeSearchResponse:
    """Search the current user's indexed knowledge.

    检索当前用户已经索引的知识内容。
    """

    _ensure_rag_enabled()
    results = await KnowledgeService().search(
        query=request.query,
        limit=request.limit,
        context=context,
    )
    return KnowledgeSearchResponse(results=results)


def _ensure_rag_enabled() -> None:
    """Reject RAG requests until the operator enables RAG explicitly.

    在运维人员显式开启 RAG 前拒绝相关请求。
    """

    if not settings.RAG_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG is disabled. Set RAG_ENABLED=true to enable knowledge APIs.",
        )
