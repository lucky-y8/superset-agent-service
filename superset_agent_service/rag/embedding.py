"""Embedding client for DashScope/OpenAI-compatible embedding APIs.

用于 DashScope/OpenAI 兼容向量接口的 Embedding 客户端。
"""

import logging

import httpx

from superset_agent_service.config import settings

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Create semantic vectors for text chunks.

    为文本切片生成语义向量。
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        """Store provider settings without logging secrets.

        保存供应商配置，但不会把密钥写入日志。
        """

        self.api_key = api_key or settings.DASHSCOPE_API_KEY
        self.model = model or settings.EMBEDDING_MODEL
        self.endpoint = endpoint or settings.DASHSCOPE_EMBEDDING_URL

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in one provider request when possible.

        尽可能在一次供应商请求中为多段文本生成向量。
        """

        if not texts:
            return []
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured.")

        payload = {"model": self.model, "input": texts}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(self.endpoint, json=payload, headers=headers)
        if response.status_code >= 400:
            body = response.text[:500]
            logger.warning(
                "Embedding provider rejected request: status=%s body=%s",
                response.status_code,
                body,
            )
            raise RuntimeError(f"Embedding request failed: HTTP {response.status_code}")

        data = response.json()
        embeddings: list[list[float]] = []
        for item in data.get("data", []):
            vector = item.get("embedding")
            if isinstance(vector, list):
                embeddings.append([float(value) for value in vector])
        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Embedding provider returned {len(embeddings)} vectors for "
                f"{len(texts)} texts."
            )
        return embeddings
