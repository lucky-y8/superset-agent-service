"""Response schemas for the Usage Dashboard.

Usage Dashboard 使用的响应数据结构。
"""

from pydantic import BaseModel, Field


class UsageTotals(BaseModel):
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    average_duration_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    average_model_latency_ms: float = 0.0
    evaluation_pass_rate: float = 0.0


class UsageTrendPoint(BaseModel):
    date: str
    runs: int = 0
    completed: int = 0
    failed: int = 0
    tokens: int = 0
    cost_usd: float = 0.0


class ModelUsage(BaseModel):
    provider: str
    model: str
    calls: int = 0
    failed_calls: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    average_latency_ms: float = 0.0


class ToolUsage(BaseModel):
    tool: str
    completed: int = 0
    failed: int = 0
    blocked: int = 0


class ErrorUsage(BaseModel):
    message: str
    count: int


class EvaluationUsage(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    average_score: float = 0.0


class UsageDashboard(BaseModel):
    """Collect all sections needed by the operational dashboard.

    汇总运营看板一次加载所需的全部数据分区。
    """

    period_days: int
    totals: UsageTotals
    trend: list[UsageTrendPoint] = Field(default_factory=list)
    models: list[ModelUsage] = Field(default_factory=list)
    tools: list[ToolUsage] = Field(default_factory=list)
    errors: list[ErrorUsage] = Field(default_factory=list)
    evaluations: EvaluationUsage = Field(default_factory=EvaluationUsage)
