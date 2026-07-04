"""Metrics collection boundary for model usage, cost, and latency.

收集模型用量、成本和延迟指标的边界。
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from superset_agent_service.db.session import AsyncSessionLocal
from superset_agent_service.metrics.models import AgentMetricModel

logger = logging.getLogger("superset_agent_service.metrics")
SessionFactory = async_sessionmaker[AsyncSession]


class MetricsCollector:
    """Persist model-call measurements and mirror them to structured logs.

    持久化模型调用指标，并同步输出结构化日志。
    """

    def __init__(self, session_factory: SessionFactory = AsyncSessionLocal) -> None:
        """Create a collector bound to the configured database session factory.

        创建绑定到当前数据库会话工厂的指标采集器。
        """

        self.session_factory = session_factory

    async def record_model_call(
        self,
        run_id: str,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
        cost_usd: float | None = None,
        status: str = "succeeded",
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record token usage, latency, status, and optional estimated cost.

        记录 Token 用量、调用延迟、状态和可选的预估成本。
        """

        effective_total = total_tokens
        if effective_total is None:
            effective_total = input_tokens + output_tokens
        async with self.session_factory() as session:
            session.add(
                AgentMetricModel(
                    run_id=run_id,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=effective_total,
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                    status=status,
                    error_message=error_message,
                    details=details or {},
                )
            )
            await session.commit()

        logger.info(
            "model_call run=%s provider=%s model=%s input_tokens=%s output_tokens=%s total_tokens=%s latency_ms=%s cost_usd=%s status=%s",
            run_id,
            provider,
            model,
            input_tokens,
            output_tokens,
            effective_total,
            latency_ms,
            cost_usd,
            status,
        )
