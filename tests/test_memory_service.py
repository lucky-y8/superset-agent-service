"""Unit tests for durable Agent long-term memory.

Agent 长期记忆持久化能力的单元测试。
"""

import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.db.base import Base
from superset_agent_service.memory.service import MemoryService


class MemoryServiceTests(unittest.IsolatedAsyncioTestCase):
    """Verify user-scoped memory read and write behavior.

    验证按用户隔离的记忆读写行为。
    """

    async def asyncSetUp(self) -> None:
        """Create an isolated in-memory database for each test.

        为每个测试创建隔离的内存数据库。
        """

        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.service = MemoryService(session_factory=self.sessions)

    async def asyncTearDown(self) -> None:
        """Dispose the isolated database engine.

        释放隔离数据库引擎。
        """

        await self.engine.dispose()

    async def test_upsert_and_list_memory_for_current_user(self):
        """A user can write and read back their own memory.

        用户可以写入并读取自己的记忆。
        """

        context = PermissionContext(user_id="u1", tenant_id="tenant-a")

        saved = await self.service.upsert_memory(
            context=context,
            memory_type="preference",
            memory_key="chart_language",
            memory_value={"value": "zh-CN"},
            source="test",
        )
        memories = await self.service.list_memories(context=context)

        self.assertEqual(saved.memory_key, "chart_language")
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0].memory_value, {"value": "zh-CN"})

    async def test_memories_are_isolated_by_user(self):
        """One user cannot see another user's memory.

        一个用户不能读取另一个用户的记忆。
        """

        await self.service.upsert_memory(
            context=PermissionContext(user_id="u1"),
            memory_type="preference",
            memory_key="theme",
            memory_value={"value": "compact"},
        )

        memories = await self.service.list_memories(
            context=PermissionContext(user_id="u2")
        )

        self.assertEqual(memories, [])

    async def test_tool_result_extracts_recent_dashboard(self):
        """Dashboard tool results update the latest dashboard resource memory.

        看板工具结果会更新最近看板资源记忆。
        """

        context = PermissionContext(user_id="u1")

        writes = await self.service.remember_tool_result(
            context=context,
            tool_name="list_dashboards",
            result={
                "content": [
                    {
                        "type": "text",
                        "text": '{"dashboards":[{"id":7,"dashboard_title":"销售看板"}]}',
                    }
                ]
            },
        )
        runtime_context = await self.service.get_runtime_context(context=context)

        self.assertGreaterEqual(len(writes), 2)
        self.assertEqual(runtime_context["resources"]["last_dashboard"]["id"], "7")
        self.assertEqual(
            runtime_context["resources"]["last_dashboard"]["title"],
            "销售看板",
        )


if __name__ == "__main__":
    unittest.main()
