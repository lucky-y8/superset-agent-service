# db_extension.py (或者可以命名为 database.py)

import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base # 仍然使用这个来定义模型
from sqlalchemy.orm import sessionmaker

# 声明式基类：用于定义所有 SQLAlchemy 模型
# 这是一个全局对象，因为所有模型都会继承它
Base = declarative_base()

class AsyncSQLAlchemyExtension:
    """
    为 FastAPI 应用管理异步 SQLAlchemy 的扩展。
    负责初始化异步引擎、会话工厂，并提供数据库会话的依赖注入。
    """
    def __init__(self, db_url: str):
        """
        初始化 AsyncSQLAlchemyExtension。
        Args:
            db_url: 数据库连接字符串 (例如 "sqlite+aiosqlite:///./test.db")。
        """
        self.engine = create_async_engine(db_url, echo=True) # echo=True 方便调试
        self.AsyncSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            class_=AsyncSession, # 关键：指定会话类为 AsyncSession
        )

    async def create_db_and_tables(self) -> None:
        """
        异步创建所有在 Base 中定义的数据库表。
        此方法通常在 FastAPI 应用启动时调用。
        """
        async with self.engine.begin() as conn:
            # 在异步连接中运行同步的 Base.metadata.create_all
            await conn.run_sync(Base.metadata.create_all)

    async def get_db(self) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI 依赖注入函数：为每个请求提供一个独立的异步数据库会话。
        这个函数是异步生成器，FastAPI 会自动管理会话的生命周期。
        """
        async with self.AsyncSessionLocal() as session:
            yield session

# 示例用法：
# db_url = "sqlite+aiosqlite:///./test.db"
# async_db_ext = AsyncSQLAlchemyExtension(db_url)
#
# # 数据库模型定义 (在 models.py 中，或者直接在这里作为示例)
# # from sqlalchemy import Column, Integer, String
# # class User(Base):
# #     __tablename__ = "users"
# #     id = Column(Integer, primary_key=True, index=True)
# #     name = Column(String)