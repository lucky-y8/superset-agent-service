"""Async SQLAlchemy engine and session dependency.

异步 SQLAlchemy 引擎与会话依赖。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from superset_agent_service.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield one database session and close it after the request finishes.

    提供一次数据库会话，并在请求结束后自动关闭。
    """

    async with AsyncSessionLocal() as session:
        yield session
