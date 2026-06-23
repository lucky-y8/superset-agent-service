"""Application service for knowledge ingestion and semantic retrieval.

知识入库与语义检索的应用服务。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.config import settings
from superset_agent_service.db.session import AsyncSessionLocal
from superset_agent_service.rag.embedding import EmbeddingClient
from superset_agent_service.rag.models import KnowledgeChunkModel, KnowledgeDocumentModel
from superset_agent_service.rag.schemas import KnowledgeDocument, KnowledgeSearchResult
from superset_agent_service.rag.storage import OSSStorage
from superset_agent_service.rag.text import chunk_text, extract_text
from superset_agent_service.rag.vector_store import QdrantVectorStore

SessionFactory = async_sessionmaker[AsyncSession]


class KnowledgeService:
    """Coordinate OSS, PostgreSQL, embedding, and Qdrant for RAG.

    协调 OSS、PostgreSQL、Embedding 与 Qdrant，完成 RAG 知识库能力。
    """

    def __init__(
        self,
        session_factory: SessionFactory = AsyncSessionLocal,
        embedding: EmbeddingClient | None = None,
        vector_store: QdrantVectorStore | None = None,
    ) -> None:
        """Create service dependencies that can be replaced in tests.

        创建可在测试中替换的服务依赖。
        """

        self.session_factory = session_factory
        self.embedding = embedding or EmbeddingClient()
        self.vector_store = vector_store or QdrantVectorStore()

    async def ingest_file(
        self,
        *,
        filename: str,
        content_type: str | None,
        data: bytes,
        context: PermissionContext,
    ) -> KnowledgeDocument:
        """Store, parse, embed, and index one uploaded file.

        存储、解析、向量化并索引一个上传文件。
        """

        document_id = str(uuid4())
        safe_name = Path(filename).name or f"{document_id}.txt"
        object_key = (
            f"{settings.OSS_PREFIX.strip('/')}/"
            f"{context.user_id}/{document_id}/{safe_name}"
        )
        document = KnowledgeDocumentModel(
            document_id=document_id,
            filename=safe_name,
            content_type=content_type,
            object_key=object_key,
            owner_user_id=context.user_id,
            owner_username=context.username,
            access_scope="owner",
            status="created",
            chunk_count=0,
            extra_metadata={"source": "upload"},
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )

        async with self.session_factory() as session:
            session.add(document)
            await session.commit()

        try:
            await self._upload_original(object_key, data, content_type)
            text = extract_text(safe_name, data)
            chunks = chunk_text(text)
            if not chunks:
                raise ValueError("No readable text was extracted from the file.")
            vectors = await self.embedding.embed_texts(chunks)
            chunk_models, points = self._build_chunks_and_points(
                document=document,
                chunks=chunks,
                vectors=vectors,
            )
            async with self.session_factory() as session:
                session.add_all(chunk_models)
                stored = await session.get(KnowledgeDocumentModel, document_id)
                if stored is None:
                    raise RuntimeError("Knowledge document disappeared during ingest.")
                stored.status = "indexed"
                stored.chunk_count = len(chunk_models)
                stored.updated_at = _utc_now()
                await session.commit()
            await self.vector_store.upsert_chunks(points)
        except Exception as exc:
            async with self.session_factory() as session:
                stored = await session.get(KnowledgeDocumentModel, document_id)
                if stored is not None:
                    stored.status = "failed"
                    stored.error_message = str(exc)
                    stored.updated_at = _utc_now()
                    await session.commit()
                    return _to_schema(stored)
            raise

        async with self.session_factory() as session:
            stored = await session.get(KnowledgeDocumentModel, document_id)
            if stored is None:
                raise RuntimeError("Knowledge document was not found after ingest.")
            return _to_schema(stored)

    async def list_documents(self, context: PermissionContext) -> list[KnowledgeDocument]:
        """List knowledge documents visible to the current user.

        列出当前用户可见的知识文档。
        """

        async with self.session_factory() as session:
            rows = await session.scalars(
                select(KnowledgeDocumentModel)
                .where(KnowledgeDocumentModel.owner_user_id == context.user_id)
                .order_by(KnowledgeDocumentModel.created_at.desc())
            )
            return [_to_schema(row) for row in rows]

    async def search(
        self,
        *,
        query: str,
        limit: int,
        context: PermissionContext,
    ) -> list[KnowledgeSearchResult]:
        """Run permission-scoped semantic search over indexed chunks.

        在已经索引的文本切片上执行按权限限定的语义检索。
        """

        vector = (await self.embedding.embed_texts([query]))[0]
        hits = await self.vector_store.search(
            vector,
            owner_user_id=context.user_id,
            limit=limit,
        )
        return [
            KnowledgeSearchResult(
                document_id=str(hit.get("document_id", "")),
                chunk_id=str(hit.get("chunk_id", "")),
                filename=str(hit.get("filename", "")),
                text=str(hit.get("text", "")),
                score=float(hit["score"]) if hit.get("score") is not None else None,
                metadata={
                    key: value
                    for key, value in hit.items()
                    if key not in {"document_id", "chunk_id", "filename", "text", "score"}
                },
            )
            for hit in hits
            if hit.get("text")
        ]

    async def _upload_original(
        self,
        object_key: str,
        data: bytes,
        content_type: str | None,
    ) -> None:
        """Upload the original file and always close the OSS client.

        上传原始文件，并确保关闭 OSS 客户端。
        """

        storage = OSSStorage()
        try:
            await storage.put_bytes(object_key, data, content_type)
        finally:
            await storage.close()

    def _build_chunks_and_points(
        self,
        *,
        document: KnowledgeDocumentModel,
        chunks: list[str],
        vectors: list[list[float]],
    ) -> tuple[list[KnowledgeChunkModel], list[tuple[str, list[float], dict[str, object]]]]:
        """Create database rows and Qdrant points for embedded chunks.

        为已经向量化的文本切片创建数据库行与 Qdrant 点。
        """

        chunk_models: list[KnowledgeChunkModel] = []
        points: list[tuple[str, list[float], dict[str, object]]] = []
        for index, (text, vector) in enumerate(zip(chunks, vectors), start=1):
            chunk_id = str(uuid4())
            metadata = {
                "chunk_index": index,
                "object_key": document.object_key,
            }
            chunk_models.append(
                KnowledgeChunkModel(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    chunk_index=index,
                    text=text,
                    owner_user_id=document.owner_user_id,
                    access_scope=document.access_scope,
                    extra_metadata=metadata,
                    created_at=_utc_now(),
                )
            )
            points.append(
                (
                    chunk_id,
                    vector,
                    {
                        "chunk_id": chunk_id,
                        "document_id": document.document_id,
                        "filename": document.filename,
                        "text": text,
                        "owner_user_id": document.owner_user_id,
                        "access_scope": document.access_scope,
                        **metadata,
                    },
                )
            )
        return chunk_models, points


def _to_schema(model: KnowledgeDocumentModel) -> KnowledgeDocument:
    """Convert an ORM model into its API schema.

    将 ORM 模型转换为 API 数据结构。
    """

    return KnowledgeDocument(
        document_id=model.document_id,
        filename=model.filename,
        content_type=model.content_type,
        status=model.status,
        owner_user_id=model.owner_user_id,
        access_scope=model.access_scope,
        chunk_count=model.chunk_count,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp.

    返回当前带 UTC 时区信息的时间戳。
    """

    return datetime.now(UTC)
