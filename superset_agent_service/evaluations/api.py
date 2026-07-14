"""HTTP API for evaluation case management and automatic scoring.

评估用例管理和自动评分 HTTP 接口。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from superset_agent_service.agents.schemas import AgentRequest
from superset_agent_service.agents.service import AgentService
from superset_agent_service.auth.dependencies import get_permission_context
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.evaluations.schemas import (
    EvaluationCase,
    EvaluationCaseCreate,
    EvaluationExecution,
    EvaluationResult,
    EvaluationRunRequest,
)
from superset_agent_service.evaluations.service import EvaluationService

router = APIRouter()


def _require_admin(context: PermissionContext) -> None:
    """Restrict quality baselines to administrators.

    仅允许管理员维护质量基线和执行评估。
    """

    if not context.is_admin:
        raise HTTPException(status_code=403, detail="Administrator role required")


@router.post("/cases", response_model=EvaluationCase, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: EvaluationCaseCreate,
    context: PermissionContext = Depends(get_permission_context),
) -> EvaluationCase:
    _require_admin(context)
    return await EvaluationService().create_case(payload, context.user_id)


@router.get("/cases", response_model=list[EvaluationCase])
async def list_cases(
    enabled_only: bool = False,
    context: PermissionContext = Depends(get_permission_context),
) -> list[EvaluationCase]:
    _require_admin(context)
    return await EvaluationService().list_cases(enabled_only)


@router.post("/cases/{case_id}/evaluate", response_model=EvaluationResult)
async def evaluate_run(
    case_id: str,
    payload: EvaluationRunRequest,
    context: PermissionContext = Depends(get_permission_context),
) -> EvaluationResult:
    _require_admin(context)
    try:
        return await EvaluationService().evaluate_run(
            case_id, payload.run_id, context.user_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/cases/{case_id}/execute", response_model=EvaluationExecution)
async def execute_case(
    case_id: str,
    context: PermissionContext = Depends(get_permission_context),
) -> EvaluationExecution:
    """Run one enabled case through the real Agent and score it immediately.

    使用真实 Agent 自动执行一个已启用用例，并在完成后立即评分。
    """

    _require_admin(context)
    evaluations = EvaluationService()
    case = await evaluations.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Evaluation case not found")
    if not case.enabled:
        raise HTTPException(status_code=409, detail="Evaluation case is disabled")

    supported_context = {
        key: value
        for key, value in case.request_context.items()
        if key in {"dashboard_id", "chart_id", "filters", "time_range"}
    }
    response = await AgentService().chat(
        AgentRequest(question=case.question, **supported_context), context
    )
    result = await evaluations.evaluate_run(
        case_id, response.run_id, evaluated_by=context.user_id
    )
    return EvaluationExecution(
        run_id=response.run_id,
        answer=response.answer,
        evaluation=result,
    )


@router.get("/results", response_model=list[EvaluationResult])
async def list_results(
    case_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    context: PermissionContext = Depends(get_permission_context),
) -> list[EvaluationResult]:
    _require_admin(context)
    return await EvaluationService().list_results(case_id, limit)
