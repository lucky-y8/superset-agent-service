"""Object storage adapter for Aliyun OSS.

阿里云 OSS 对象存储适配器。
"""

import os

import alibabacloud_oss_v2 as oss
import alibabacloud_oss_v2.aio as oss_aio

from superset_agent_service.config import settings


class OSSStorage:
    """Store original knowledge files in Aliyun OSS.

    将知识库原始文件保存到阿里云 OSS。
    """

    def __init__(self) -> None:
        """Initialize an async OSS client from application settings.

        使用应用配置初始化异步 OSS 客户端。
        """

        if not settings.OSS_BUCKET:
            raise RuntimeError("OSS_BUCKET is not configured.")
        if not settings.OSS_REGION:
            raise RuntimeError("OSS_REGION is not configured.")
        if not settings.OSS_ACCESS_KEY_ID or not settings.OSS_ACCESS_KEY_SECRET:
            raise RuntimeError("OSS access key is not configured.")

        # The official V2 SDK environment provider reads process variables.
        # Pydantic loads .env into settings, so we mirror only these two values
        # into os.environ for SDK initialization.
        # 官方 V2 SDK 的环境变量凭证提供者读取进程环境变量。Pydantic 会把 .env 加载到
        # settings，因此这里仅把 OSS 凭证同步到 os.environ 供 SDK 初始化使用。
        os.environ.setdefault("OSS_ACCESS_KEY_ID", settings.OSS_ACCESS_KEY_ID)
        os.environ.setdefault("OSS_ACCESS_KEY_SECRET", settings.OSS_ACCESS_KEY_SECRET)

        credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = settings.OSS_REGION
        if settings.OSS_ENDPOINT:
            cfg.endpoint = settings.OSS_ENDPOINT
        self.bucket = settings.OSS_BUCKET
        self.client = oss_aio.AsyncClient(cfg)

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> None:
        """Upload raw bytes to OSS under the provided object key.

        将原始字节内容上传到 OSS 指定对象路径。
        """

        request = oss.PutObjectRequest(
            bucket=self.bucket,
            key=key,
            body=data,
            content_type=content_type,
        )
        result = await self.client.put_object(request)
        if result.status_code >= 400:
            raise RuntimeError(f"OSS upload failed: HTTP {result.status_code}")

    async def close(self) -> None:
        """Close the underlying asynchronous OSS client.

        关闭底层异步 OSS 客户端。
        """

        await self.client.close()
