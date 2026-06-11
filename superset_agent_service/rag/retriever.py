"""Retrieval boundary for future business knowledge and metadata search.

为未来业务知识与元数据检索预留的边界。
"""

class RAGRetriever:
    """Define the asynchronous interface for future retrieval backends.

    定义未来检索后端需要实现的异步接口。
    """

    async def search(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        """Return matching knowledge records; currently no backend is connected.

        返回匹配的知识记录；当前尚未接入实际检索后端。
        """

        return []
