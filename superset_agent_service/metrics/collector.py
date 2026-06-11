"""Metrics collection boundary for model usage, cost, and latency.

收集模型用量、成本和延迟指标的边界。
"""

import logging

logger = logging.getLogger("superset_agent_service.metrics")


class MetricsCollector:
    """Emit model-call measurements for a future metrics backend.

    输出模型调用指标，以便以后接入正式监控后端。
    """

    async def record_model_call(
        self,
        run_id: str,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        """Record token usage, latency, and optional estimated cost.

        记录 Token 用量、调用延迟和可选的预估成本。
        """

        logger.info(
            "model_call run=%s provider=%s model=%s input_tokens=%s output_tokens=%s latency_ms=%s cost_usd=%s",
            run_id,
            provider,
            model,
            input_tokens,
            output_tokens,
            latency_ms,
            cost_usd,
        )
