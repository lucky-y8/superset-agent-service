from logging.config import fileConfig
import asyncio
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from os.path import abspath, dirname
from alembic import context

# 导入你的配置和模型
import sys
from pathlib import Path

# 添加项目路径到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from legacy_user_service.config import settings
from legacy_user_service.extensions.db_extension import Base

# 导入所有模型（确保 Alembic 能检测到）
from legacy_user_service.models.users import User
# 未来添加更多模型时在这里导入
# from legacy_user_service.models.sentiment import Sentiment
# from legacy_user_service.models.article import Article

# Alembic Config 对象
config = context.config

# 设置数据库连接 URL
config.set_main_option('sqlalchemy.url', str(settings.SQLALCHEMY_DATABASE_URI))

# 解释 Python 日志配置文件
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置 target_metadata 为你的 Base.metadata
target_metadata = Base.metadata

# 其他值从 Alembic 配置中获取


def run_migrations_offline() -> None:
    """
    离线模式：生成 SQL 脚本而不连接数据库
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    执行迁移的核心函数
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    异步模式：连接数据库并执行迁移
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    在线模式：运行异步迁移
    """
    # 针对 Windows 的修复
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_async_migrations())


# 判断运行模式
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

