"""Qdrant-backed semantic long-term memory for Agent conversations.

基于 Qdrant 的 Agent 对话语义长期记忆。
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from qdrant_client import AsyncQdrantClient, models

from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.config import settings
from superset_agent_service.rag.embedding import EmbeddingClient


class SemanticMemoryService:
    """Store and retrieve conversation memories as vectors in Qdrant.

    将对话记忆作为向量写入 Qdrant，并按语义检索。
    """

    def __init__(
        self,
        embedding: EmbeddingClient | None = None,
        client: AsyncQdrantClient | None = None,
        collection: str | None = None,
    ) -> None:
        """Create a semantic memory service with replaceable dependencies.

        创建依赖可替换的语义记忆服务。
        """

        self.embedding = embedding or EmbeddingClient()
        self.collection = collection or settings.QDRANT_MEMORY_COLLECTION
        self.client = client or AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
        )

    async def get_runtime_context(
        self,
        *,
        query: str,
        context: PermissionContext,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Search semantically similar past conversations for the prompt.

        为 Prompt 检索语义相似的历史对话。
        """

        memories = await self.search_conversations(
            query=query,
            context=context,
            limit=limit or settings.SEMANTIC_MEMORY_TOP_K,
        )
        return {"semantic_conversations": memories}

    async def remember_conversation(
        self,
        *,
        context: PermissionContext,
        question: str,
        answer: str,
        run_id: str | None = None,
    ) -> str:
        """Vectorize and store one completed Agent conversation.

        将一次完成的 Agent 对话向量化并存入 Qdrant。
        """

        await self.ensure_collection()
        text = _conversation_text(question=question, answer=answer)
        vector = (await self.embedding.embed_texts([text]))[0]
        memory_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        await self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload={
                        "memory_id": memory_id,
                        "memory_type": "conversation",
                        "user_id": context.user_id,
                        "tenant_id": context.tenant_id or "",
                        "username": context.username,
                        "run_id": run_id,
                        "question": question,
                        "answer": answer[:4000],
                        "text": text[:6000],
                        "created_at": created_at,
                    },
                )
            ],
        )
        return memory_id

    async def search_conversations(
        self,
        *,
        query: str,
        context: PermissionContext,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search prior conversations owned by the current user.

        检索当前用户拥有的历史对话记忆。
        """

        await self.ensure_collection()
        vector = (await self.embedding.embed_texts([query]))[0]
        response = await self.client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=context.user_id),
                    ),
                    models.FieldCondition(
                        key="tenant_id",
                        match=models.MatchValue(value=context.tenant_id or ""),
                    ),
                    models.FieldCondition(
                        key="memory_type",
                        match=models.MatchValue(value="conversation"),
                    ),
                ]
            ),
            limit=limit,
            with_payload=True,
        )
        memories: list[dict[str, Any]] = []
        for point in response.points:
            payload = dict(point.payload or {})
            payload["score"] = point.score
            memories.append(payload)
        return memories

    async def ensure_collection(self) -> None:
        """Create the memory collection when it does not exist.

        当记忆集合不存在时自动创建。
        """

        collections = await self.client.get_collections()
        names = {collection.name for collection in collections.collections}
        if self.collection in names:
            return
        await self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=settings.EMBEDDING_DIM,
                distance=models.Distance.COSINE,
            ),
        )


def _conversation_text(*, question: str, answer: str) -> str:
    """Build the text that will be embedded as semantic memory.

    构造用于生成语义记忆向量的文本。
    """

    return f"用户问题:\n{question}\n\nAgent回答:\n{answer}"
