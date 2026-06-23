"""Unit tests for Qdrant-backed semantic conversation memory.

基于 Qdrant 的对话语义记忆单元测试。
"""

import unittest
from types import SimpleNamespace

from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.memory.semantic import SemanticMemoryService


class FakeEmbedding:
    """Return deterministic vectors without calling an embedding provider.

    返回确定性向量，不调用真实向量模型服务。
    """

    async def embed_texts(self, texts):
        """Return one small vector per text.

        为每段文本返回一个小向量。
        """

        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeQdrantClient:
    """Minimal async Qdrant replacement used by semantic memory tests.

    语义记忆测试使用的最小异步 Qdrant 替身。
    """

    def __init__(self):
        """Store collection names and upserted points in memory.

        在内存中保存集合名称和写入的点。
        """

        self.collections = set()
        self.points = []
        self.last_filter = None

    async def get_collections(self):
        """Return fake collection metadata.

        返回假的集合元数据。
        """

        return SimpleNamespace(
            collections=[SimpleNamespace(name=name) for name in self.collections]
        )

    async def create_collection(self, collection_name, vectors_config):
        """Create a fake collection.

        创建一个假的集合。
        """

        self.collections.add(collection_name)

    async def upsert(self, collection_name, points):
        """Store points written by the service.

        保存服务写入的点。
        """

        self.collections.add(collection_name)
        self.points.extend(points)

    async def query_points(
        self,
        collection_name,
        query,
        query_filter,
        limit,
        with_payload,
    ):
        """Return stored points as scored query results.

        将已保存的点作为带分数的查询结果返回。
        """

        self.last_filter = query_filter
        return SimpleNamespace(
            points=[
                SimpleNamespace(payload=point.payload, score=0.91)
                for point in self.points[:limit]
            ]
        )


class SemanticMemoryTests(unittest.IsolatedAsyncioTestCase):
    """Verify conversation memory is stored and searched through Qdrant.

    验证对话记忆会通过 Qdrant 写入和检索。
    """

    async def test_remember_conversation_writes_vector_payload(self):
        """A completed conversation is vectorized and stored as Qdrant payload.

        完成的一轮对话会被向量化并作为 Qdrant payload 保存。
        """

        client = FakeQdrantClient()
        service = SemanticMemoryService(
            embedding=FakeEmbedding(),
            client=client,
            collection="test_memory",
        )

        memory_id = await service.remember_conversation(
            context=PermissionContext(user_id="u1", tenant_id="tenant-a"),
            question="刚才的数据集是什么？",
            answer="最近的数据集 ID 是 12。",
            run_id="run-1",
        )

        self.assertTrue(memory_id)
        self.assertEqual(len(client.points), 1)
        payload = client.points[0].payload
        self.assertEqual(payload["memory_type"], "conversation")
        self.assertEqual(payload["user_id"], "u1")
        self.assertEqual(payload["tenant_id"], "tenant-a")
        self.assertEqual(payload["run_id"], "run-1")
        self.assertIn("刚才的数据集是什么？", payload["text"])

    async def test_search_conversations_returns_scored_memories(self):
        """Search returns semantic memory payloads with similarity scores.

        检索会返回带相似度分数的语义记忆 payload。
        """

        client = FakeQdrantClient()
        service = SemanticMemoryService(
            embedding=FakeEmbedding(),
            client=client,
            collection="test_memory",
        )
        context = PermissionContext(user_id="u1")
        await service.remember_conversation(
            context=context,
            question="我要中文图表名",
            answer="后续图表名称会优先使用中文。",
        )

        memories = await service.search_conversations(
            query="我之前说图表名要什么语言？",
            context=context,
            limit=5,
        )

        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["memory_type"], "conversation")
        self.assertEqual(memories[0]["score"], 0.91)
        self.assertIsNotNone(client.last_filter)


if __name__ == "__main__":
    unittest.main()
