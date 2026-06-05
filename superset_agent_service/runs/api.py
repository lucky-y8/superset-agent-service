"""HTTP endpoints for inspecting agent run traces."""

from fastapi import APIRouter, HTTPException

from superset_agent_service.runs.schemas import RunTrace
from superset_agent_service.runs.service import RunService

router = APIRouter()


@router.get("/{run_id}", response_model=RunTrace)
async def get_run_trace(run_id: str) -> RunTrace:
    trace = RunService.get_trace(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return trace
