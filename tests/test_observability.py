"""Persistence tests for Agent metrics and audit logs.

Agent 指标和审计日志的持久化测试。
"""

import unittest

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.audit.logger import AuditLogger
from superset_agent_service.audit.models import AgentAuditLogModel
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.db.base import Base
from superset_agent_service.metrics.collector import MetricsCollector
from superset_agent_service.metrics.models import AgentMetricModel
from superset_agent_service.runs.service import RunService


class ObservabilityPersistenceTests(unittest.IsolatedAsyncioTestCase):
    """Verify Metrics and Audit write durable database rows.

    验证 Metrics 和 Audit 会写入真实数据库记录。
    """

    async def asyncSetUp(self) -> None:
        """Create an isolated in-memory database for each test.

        为每个测试创建独立的内存数据库。
        """

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        self.runs = RunService(session_factory=self.sessions)
        self.runs.bind_run("observability-run", "u1")
        await self.runs.start_run(
            AgentRequest(question="查询看板"),
            PermissionContext(user_id="u1", username="test2", roles=["Gamma"]),
        )

    async def asyncTearDown(self) -> None:
        """Dispose the isolated test database engine.

        释放测试数据库引擎。
        """

        await self.engine.dispose()

    async def test_metrics_collector_persists_model_call(self) -> None:
        """Persist token, latency, model, and status metrics.

        持久化 Token、延迟、模型和状态指标。
        """

        collector = MetricsCollector(session_factory=self.sessions)
        await collector.record_model_call(
            run_id="observability-run",
            provider="deepseek",
            model="deepseek-chat",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            latency_ms=1234,
            details={"usage_available": True},
        )

        async with self.sessions() as session:
            metric = await session.scalar(select(AgentMetricModel))

        self.assertIsNotNone(metric)
        self.assertEqual(metric.run_id, "observability-run")
        self.assertEqual(metric.provider, "deepseek")
        self.assertEqual(metric.model, "deepseek-chat")
        self.assertEqual(metric.total_tokens, 15)
        self.assertEqual(metric.latency_ms, 1234)
        self.assertEqual(metric.status, "succeeded")
        self.assertEqual(metric.details["usage_available"], True)

    async def test_audit_logger_persists_security_event(self) -> None:
        """Persist who did what against which resource.

        持久化谁对哪个资源执行了什么动作。
        """

        audit = AuditLogger(session_factory=self.sessions)
        await audit.record_context(
            PermissionContext(
                user_id="u1",
                username="test2",
                tenant_id="tenant-a",
                roles=["Gamma"],
            ),
            action="tool_completed",
            resource_type="mcp_tool",
            resource_id="list_dashboards",
            run_id="observability-run",
            metadata={"result_count": 1},
        )

        async with self.sessions() as session:
            audit_log = await session.scalar(select(AgentAuditLogModel))

        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.run_id, "observability-run")
        self.assertEqual(audit_log.user_id, "u1")
        self.assertEqual(audit_log.username, "test2")
        self.assertEqual(audit_log.tenant_id, "tenant-a")
        self.assertEqual(audit_log.action, "tool_completed")
        self.assertEqual(audit_log.resource_id, "list_dashboards")
        self.assertEqual(audit_log.outcome, "success")
        self.assertEqual(audit_log.event_metadata["result_count"], 1)


if __name__ == "__main__":
    unittest.main()
