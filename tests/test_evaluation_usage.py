"""Tests for deterministic evaluation and Usage Dashboard aggregation.

确定性自动评估与 Usage Dashboard 聚合测试。
"""

import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.audit.logger import AuditLogger
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.db.base import Base
from superset_agent_service.evaluations.schemas import EvaluationCaseCreate
from superset_agent_service.evaluations.service import EvaluationService
from superset_agent_service.metrics.collector import MetricsCollector
from superset_agent_service.runs.service import RunService
from superset_agent_service.usage.service import UsageService


class EvaluationAndUsageTests(unittest.IsolatedAsyncioTestCase):
    """Verify scoring evidence and dashboard metrics share persisted facts.

    验证评估证据和运营看板指标使用同一份持久化事实数据。
    """

    async def asyncSetUp(self) -> None:
        """Create one isolated database and a completed Agent run.

        创建隔离数据库以及一条已完成的 Agent 运行记录。
        """

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        self.context = PermissionContext(
            user_id="admin-1", username="admin", roles=["Admin"]
        )
        self.runs = RunService(session_factory=self.sessions)
        self.runs.bind_run("evaluation-run", self.context.user_id)
        await self.runs.start_run(
            AgentRequest(question="查询前五个仪表盘"), self.context
        )
        await self.runs.record_event(
            "tool_started", {"tool": "list_dashboards", "arguments": {}}
        )
        await self.runs.record_event(
            "tool_completed", {"tool": "list_dashboards", "result": {"count": 5}}
        )
        await self.runs.record_model_usage(100, 20, 120, 0.002)
        await self.runs.complete_run(
            final_answer="已返回 5 个仪表盘，包括销售分析看板。"
        )

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def test_evaluate_run_persists_component_scores_and_evidence(self) -> None:
        """A matching answer and tool trace should pass its quality baseline.

        答案和工具轨迹均符合预期时，应通过对应质量基线。
        """

        service = EvaluationService(self.sessions)
        case = await service.create_case(
            EvaluationCaseCreate(
                name="仪表盘列表",
                question="查询前五个仪表盘",
                expected_tools=["list_dashboards"],
                expected_answer_contains=["5", "仪表盘"],
                forbidden_answer_contains=["没有权限"],
                minimum_score=0.8,
            ),
            created_by="admin-1",
        )

        result = await service.evaluate_run(
            case.case_id, "evaluation-run", evaluated_by="admin-1"
        )

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.answer_score, 1.0)
        self.assertEqual(result.tool_score, 1.0)
        self.assertEqual(result.details["observed_tools"], ["list_dashboards"])
        self.assertEqual(len(await service.list_results()), 1)

    async def test_usage_dashboard_aggregates_runs_models_tools_and_evaluations(self) -> None:
        """Usage snapshot should expose all operational dimensions together.

        Usage 快照应同时提供运行、模型、工具和评估四类运营维度。
        """

        metrics = MetricsCollector(self.sessions)
        await metrics.record_model_call(
            run_id="evaluation-run",
            provider="deepseek",
            model="deepseek-chat",
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            latency_ms=800,
            cost_usd=0.002,
        )
        audit = AuditLogger(self.sessions)
        await audit.record_context(
            self.context,
            action="tool_completed",
            resource_type="mcp_tool",
            resource_id="list_dashboards",
            run_id="evaluation-run",
        )
        evaluations = EvaluationService(self.sessions)
        case = await evaluations.create_case(
            EvaluationCaseCreate(
                name="仪表盘工具",
                question="查询仪表盘",
                expected_tools=["list_dashboards"],
            ),
            "admin-1",
        )
        await evaluations.evaluate_run(case.case_id, "evaluation-run", "admin-1")

        dashboard = await UsageService(self.sessions).dashboard(days=30)

        self.assertEqual(dashboard.totals.total_runs, 1)
        self.assertEqual(dashboard.totals.success_rate, 1.0)
        self.assertEqual(dashboard.totals.total_tokens, 120)
        self.assertEqual(dashboard.models[0].model, "deepseek-chat")
        self.assertEqual(dashboard.models[0].average_latency_ms, 800)
        self.assertEqual(dashboard.tools[0].tool, "list_dashboards")
        self.assertEqual(dashboard.tools[0].completed, 1)
        self.assertEqual(dashboard.evaluations.pass_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
