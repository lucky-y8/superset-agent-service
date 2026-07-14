"""Alembic environment for asynchronous SQLAlchemy migrations.

用于执行异步 SQLAlchemy 迁移的 Alembic 环境。
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from superset_agent_service.config import settings
from superset_agent_service.audit import models as audit_models  # noqa: F401
from superset_agent_service.db.base import Base
from superset_agent_service.evaluations import models as evaluation_models  # noqa: F401
from superset_agent_service.memory import models as memory_models  # noqa: F401
from superset_agent_service.metrics import models as metrics_models  # noqa: F401
from superset_agent_service.rag import models as rag_models  # noqa: F401
from superset_agent_service.runs import models  # noqa: F401


config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without opening a database connection.

    在不建立数据库连接的情况下生成迁移 SQL。
    """

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations through Alembic's synchronous connection facade.

    通过 Alembic 的同步连接外观执行迁移。
    """

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and execute migrations in a transaction.

    创建异步引擎，并在事务中执行迁移。
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
    """Bridge Alembic's synchronous entrypoint to the async migration task.

    将 Alembic 的同步入口桥接到异步迁移任务。
    """

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
