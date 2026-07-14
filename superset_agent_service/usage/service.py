"""Read-only aggregation service for operational Agent usage.

用于 Agent 运营指标的只读聚合服务。
"""

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from superset_agent_service.audit.models import AgentAuditLogModel
from superset_agent_service.db.session import AsyncSessionLocal
from superset_agent_service.evaluations.models import EvaluationResultModel
from superset_agent_service.metrics.models import AgentMetricModel
from superset_agent_service.runs.models import AgentRunModel
from superset_agent_service.usage.schemas import (
    ErrorUsage,
    EvaluationUsage,
    ModelUsage,
    ToolUsage,
    UsageDashboard,
    UsageTotals,
    UsageTrendPoint,
)

SessionFactory = async_sessionmaker[AsyncSession]


class UsageService:
    """Aggregate persisted facts into dashboard-ready metrics.

    将持久化事实数据聚合为前端看板可以直接展示的指标。
    """

    def __init__(self, session_factory: SessionFactory = AsyncSessionLocal) -> None:
        self.session_factory = session_factory

    async def dashboard(self, days: int = 30) -> UsageDashboard:
        """Build one bounded usage snapshot for the requested time window.

        为指定时间窗口生成一份有边界的 Usage 快照。
        """

        since = datetime.now(UTC) - timedelta(days=days)
        async with self.session_factory() as session:
            runs = (
                await session.scalars(
                    select(AgentRunModel).where(AgentRunModel.started_at >= since)
                )
            ).all()
            metrics = (
                await session.scalars(
                    select(AgentMetricModel).where(AgentMetricModel.created_at >= since)
                )
            ).all()
            audits = (
                await session.scalars(
                    select(AgentAuditLogModel).where(
                        AgentAuditLogModel.created_at >= since,
                        AgentAuditLogModel.resource_type == "mcp_tool",
                    )
                )
            ).all()
            evaluations = (
                await session.scalars(
                    select(EvaluationResultModel).where(
                        EvaluationResultModel.evaluated_at >= since
                    )
                )
            ).all()

        evaluation_usage = self._evaluation_usage(evaluations)
        return UsageDashboard(
            period_days=days,
            totals=self._totals(runs, metrics, evaluation_usage),
            trend=self._trend(runs, metrics),
            models=self._models(metrics),
            tools=self._tools(audits),
            errors=self._errors(runs),
            evaluations=evaluation_usage,
        )

    @staticmethod
    def _totals(runs, metrics, evaluations: EvaluationUsage) -> UsageTotals:
        completed = sum(run.status == "completed" for run in runs)
        failed = sum(run.status == "failed" for run in runs)
        durations = [run.duration_ms for run in runs if run.duration_ms is not None]
        latencies = [m.latency_ms for m in metrics if m.latency_ms is not None]
        return UsageTotals(
            total_runs=len(runs),
            completed_runs=completed,
            failed_runs=failed,
            success_rate=round(completed / len(runs), 4) if runs else 0.0,
            average_duration_ms=round(sum(durations) / len(durations), 2)
            if durations
            else 0.0,
            total_tokens=sum(metric.total_tokens or 0 for metric in metrics),
            total_cost_usd=round(sum(metric.cost_usd or 0.0 for metric in metrics), 6),
            average_model_latency_ms=round(sum(latencies) / len(latencies), 2)
            if latencies
            else 0.0,
            evaluation_pass_rate=evaluations.pass_rate,
        )

    @staticmethod
    def _trend(runs, metrics) -> list[UsageTrendPoint]:
        buckets: dict[str, dict[str, float]] = defaultdict(
            lambda: {"runs": 0, "completed": 0, "failed": 0, "tokens": 0, "cost": 0.0}
        )
        for run in runs:
            key = run.started_at.date().isoformat()
            buckets[key]["runs"] += 1
            if run.status == "completed":
                buckets[key]["completed"] += 1
            elif run.status == "failed":
                buckets[key]["failed"] += 1
        for metric in metrics:
            key = metric.created_at.date().isoformat()
            buckets[key]["tokens"] += metric.total_tokens or 0
            buckets[key]["cost"] += metric.cost_usd or 0.0
        return [
            UsageTrendPoint(
                date=key,
                runs=int(value["runs"]),
                completed=int(value["completed"]),
                failed=int(value["failed"]),
                tokens=int(value["tokens"]),
                cost_usd=round(value["cost"], 6),
            )
            for key, value in sorted(buckets.items())
        ]

    @staticmethod
    def _models(metrics) -> list[ModelUsage]:
        groups: dict[tuple[str, str], list] = defaultdict(list)
        for metric in metrics:
            groups[(metric.provider, metric.model)].append(metric)
        rows = []
        for (provider, model), values in groups.items():
            latencies = [item.latency_ms for item in values if item.latency_ms is not None]
            rows.append(
                ModelUsage(
                    provider=provider,
                    model=model,
                    calls=len(values),
                    failed_calls=sum(item.status != "succeeded" for item in values),
                    tokens=sum(item.total_tokens or 0 for item in values),
                    cost_usd=round(sum(item.cost_usd or 0.0 for item in values), 6),
                    average_latency_ms=round(sum(latencies) / len(latencies), 2)
                    if latencies
                    else 0.0,
                )
            )
        return sorted(rows, key=lambda item: item.calls, reverse=True)

    @staticmethod
    def _tools(audits) -> list[ToolUsage]:
        groups: dict[str, Counter] = defaultdict(Counter)
        action_map = {
            "tool_completed": "completed",
            "tool_failed": "failed",
            "tool_blocked": "blocked",
        }
        for audit in audits:
            column = action_map.get(audit.action)
            if column and audit.resource_id:
                groups[audit.resource_id][column] += 1
        return sorted(
            [
                ToolUsage(
                    tool=tool,
                    completed=counts["completed"],
                    failed=counts["failed"],
                    blocked=counts["blocked"],
                )
                for tool, counts in groups.items()
            ],
            key=lambda item: item.completed + item.failed + item.blocked,
            reverse=True,
        )

    @staticmethod
    def _errors(runs) -> list[ErrorUsage]:
        counts = Counter(
            (run.error_message or "Unknown error")[:240]
            for run in runs
            if run.status == "failed"
        )
        return [ErrorUsage(message=message, count=count) for message, count in counts.most_common(10)]

    @staticmethod
    def _evaluation_usage(results) -> EvaluationUsage:
        total = len(results)
        passed = sum(result.status == "passed" for result in results)
        failed = total - passed
        return EvaluationUsage(
            total=total,
            passed=passed,
            failed=failed,
            pass_rate=round(passed / total, 4) if total else 0.0,
            average_score=round(sum(result.score for result in results) / total, 4)
            if total
            else 0.0,
        )
