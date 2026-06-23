"""Retrieval boundary used by Agent Runtime.

Agent Runtime 使用的检索边界。
"""

from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.config import settings
from superset_agent_service.rag.service import KnowledgeService


class RAGRetriever:
    """Search business knowledge through the configured RAG backend.

    通过配置好的 RAG 后端检索业务知识。
    """

    def __init__(self, service: KnowledgeService | None = None) -> None:
        """Create a retriever with replaceable service dependency.

        创建一个服务依赖可替换的检索器。
        """

        self.service = service

    async def search(
        self,
        query: str,
        *,
        context: PermissionContext,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """Return permission-scoped matching knowledge records.

        返回经过权限限定的匹配知识记录。
        """

        if not settings.RAG_ENABLED:
            return []
        service = self.service or KnowledgeService()
        results = await service.search(
            query=query,
            limit=limit or settings.RAG_TOP_K,
            context=context,
        )
        return [result.model_dump() for result in results]
