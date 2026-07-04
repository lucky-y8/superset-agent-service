"""Persistence tests for Agent run traces.

Agent 运行轨迹的持久化测试。
"""

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.db.base import Base
from superset_agent_service.runs.service import RunService


class RunServicePersistenceTests(unittest.IsolatedAsyncioTestCase):
    """Verify run traces survive engine and service recreation.

    验证运行轨迹在数据库引擎和服务重建后仍然存在。
    """

    async def test_trace_survives_database_engine_recreation(self) -> None:
        """Write a trace, recreate the engine, and read the same events.

        写入轨迹、重建数据库引擎，然后读取同一组事件。
        """

        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "runs.db"
            database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

            first_engine = create_async_engine(database_url)
            first_sessions = async_sessionmaker(
                first_engine,
                expire_on_commit=False,
            )
            async with first_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            writer = RunService(session_factory=first_sessions)
            writer.bind_run("persistent-run", "learning-user")
            await writer.start_run(
                AgentRequest(question="查询仪表盘"),
                PermissionContext(user_id="learning-user", roles=["admin"]),
            )
            await writer.record_event(
                "tool_completed",
                {"tool": "list_dashboards"},
            )
            await writer.record_model_usage(
                input_tokens=12,
                output_tokens=8,
                total_tokens=20,
            )
            await writer.complete_run(final_answer="找到 1 个仪表盘。")
            await first_engine.dispose()

            # A new engine simulates a restarted process using the same database.
            # 新建引擎模拟进程重启后继续使用同一个数据库。
            second_engine = create_async_engine(database_url)
            second_sessions = async_sessionmaker(
                second_engine,
                expire_on_commit=False,
            )
            trace = await RunService.get_trace(
                "persistent-run",
                second_sessions,
            )
            await second_engine.dispose()

        self.assertIsNotNone(trace)
        self.assertEqual(trace.status, "completed")
        self.assertEqual(trace.user_id, "learning-user")
        self.assertEqual(trace.question, "查询仪表盘")
        self.assertEqual(trace.final_answer, "找到 1 个仪表盘。")
        self.assertIsNone(trace.error_message)
        self.assertIsNotNone(trace.started_at)
        self.assertIsNotNone(trace.completed_at)
        self.assertIsNotNone(trace.duration_ms)
        self.assertEqual(trace.input_tokens, 12)
        self.assertEqual(trace.output_tokens, 8)
        self.assertEqual(trace.total_tokens, 20)
        self.assertEqual(
            [event.event_type for event in trace.events],
            ["run_started", "tool_completed", "run_completed"],
        )

    async def test_failed_run_persists_error_summary(self) -> None:
        """Persist the final error message and timing for failed runs.

        为失败运行持久化最终错误信息和耗时。
        """

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        service = RunService(session_factory=sessions)
        service.bind_run("failed-run", "learning-user")
        await service.start_run(
            AgentRequest(question="执行危险操作"),
            PermissionContext(user_id="learning-user", roles=["admin"]),
        )
        await service.fail_run("boom")

        trace = await RunService.get_trace("failed-run", sessions)
        await engine.dispose()

        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_message, "boom")
        self.assertIsNotNone(trace.completed_at)
        self.assertIsNotNone(trace.duration_ms)


if __name__ == "__main__":
    unittest.main()
