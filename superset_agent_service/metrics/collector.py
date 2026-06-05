"""Metrics collection boundary for model usage, cost, and latency."""

import logging

logger = logging.getLogger("superset_agent_service.metrics")


class MetricsCollector:
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
