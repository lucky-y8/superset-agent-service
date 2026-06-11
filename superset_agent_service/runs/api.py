"""HTTP endpoints for inspecting agent run traces.

用于查看 Agent 运行轨迹的 HTTP 接口。
"""

from fastapi import APIRouter, HTTPException

from superset_agent_service.runs.schemas import RunTrace
from superset_agent_service.runs.service import RunService

router = APIRouter()


@router.get("/{run_id}", response_model=RunTrace)
async def get_run_trace(run_id: str) -> RunTrace:
    """Return a stored run trace or report that it does not exist.

    返回已保存的运行轨迹；不存在时返回明确的错误。
    """

    trace = RunService.get_trace(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return trace
