"""Qdrant vector-store adapter for RAG chunks.

RAG 文本切片使用的 Qdrant 向量库适配器。
"""

from typing import Any

from qdrant_client import AsyncQdrantClient, models

from superset_agent_service.config import settings


class QdrantVectorStore:
    """Write and search knowledge vectors in Qdrant.

    在 Qdrant 中写入并检索知识向量。
    """

    def __init__(self) -> None:
        """Create the async Qdrant client from environment settings.

        根据环境配置创建异步 Qdrant 客户端。
        """

        self.collection = settings.QDRANT_COLLECTION
        self.client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
        )

    async def ensure_collection(self) -> None:
        """Create the configured collection when it does not exist.

        当配置的集合不存在时自动创建。
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

    async def upsert_chunks(
        self,
        points: list[tuple[str, list[float], dict[str, Any]]],
    ) -> None:
        """Upsert embedded chunks into the configured Qdrant collection.

        将已经生成向量的文本切片写入配置的 Qdrant 集合。
        """

        if not points:
            return
        await self.ensure_collection()
        await self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(id=point_id, vector=vector, payload=payload)
                for point_id, vector, payload in points
            ],
        )

    async def search(
        self,
        vector: list[float],
        *,
        owner_user_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search chunks that belong to the current user.

        检索属于当前用户的文本切片。
        """

        await self.ensure_collection()
        result = await self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=limit,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="owner_user_id",
                        match=models.MatchValue(value=owner_user_id),
                    )
                ]
            ),
            with_payload=True,
        )
        hits: list[dict[str, Any]] = []
        for point in result.points:
            payload = dict(point.payload or {})
            payload["score"] = point.score
            hits.append(payload)
        return hits
