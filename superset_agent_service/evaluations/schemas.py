"""API schemas for evaluation cases and results.

评估用例与评估结果使用的 API 数据结构。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class EvaluationCaseCreate(BaseModel):
    """Define deterministic expectations for one evaluation question.

    定义一个评估问题的确定性期望条件。
    """

    name: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1)
    expected_tools: list[str] = Field(default_factory=list)
    expected_answer_contains: list[str] = Field(default_factory=list)
    forbidden_answer_contains: list[str] = Field(default_factory=list)
    request_context: dict[str, object] = Field(default_factory=dict)
    minimum_score: float = Field(default=0.8, ge=0.0, le=1.0)
    enabled: bool = True


class EvaluationCase(EvaluationCaseCreate):
    """Return one persisted evaluation case.

    返回一个已经持久化的评估用例。
    """

    case_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class EvaluationRunRequest(BaseModel):
    """Select the completed run that should be scored.

    指定需要自动评分的已完成运行。
    """

    run_id: str = Field(min_length=1)


class EvaluationResult(BaseModel):
    """Return component scores and evidence for one evaluation.

    返回一次评估的分项得分及判定证据。
    """

    result_id: str
    case_id: str
    run_id: str
    status: str
    score: float
    answer_score: float
    tool_score: float
    details: dict[str, object] = Field(default_factory=dict)
    evaluated_by: str
    evaluated_at: datetime


class EvaluationExecution(BaseModel):
    """Return the Agent answer together with its immediate quality score.

    返回 Agent 实际答案以及紧接着生成的质量评分。
    """

    run_id: str
    answer: str
    evaluation: EvaluationResult
