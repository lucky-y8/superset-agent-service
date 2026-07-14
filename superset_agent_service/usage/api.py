"""HTTP endpoint for the Usage Dashboard snapshot.

Usage Dashboard 快照查询接口。
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from superset_agent_service.auth.dependencies import get_permission_context
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.usage.schemas import UsageDashboard
from superset_agent_service.usage.service import UsageService

router = APIRouter()


@router.get("/dashboard", response_model=UsageDashboard)
async def get_usage_dashboard(
    days: int = Query(default=30, ge=1, le=365),
    context: PermissionContext = Depends(get_permission_context),
) -> UsageDashboard:
    """Return operational metrics to authenticated administrators.

    向已经认证的管理员返回 Agent 运营指标。
    """

    if not context.is_admin:
        raise HTTPException(status_code=403, detail="Administrator role required")
    return await UsageService().dashboard(days)
