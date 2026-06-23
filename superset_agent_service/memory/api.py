"""FastAPI routes for Agent long-term memory.

Agent 长期记忆的 FastAPI 路由。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from superset_agent_service.auth.dependencies import get_permission_context
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.memory.schemas import (
    AgentMemory,
    MemoryListResponse,
    MemoryUpsertRequest,
)
from superset_agent_service.memory.service import MemoryService

router = APIRouter()


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    memory_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    context: PermissionContext = Depends(get_permission_context),
) -> MemoryListResponse:
    """List current user's long-term memories.

    列出当前用户的长期记忆。
    """

    memories = await MemoryService().list_memories(
        context=context,
        memory_type=memory_type,
        limit=limit,
    )
    return MemoryListResponse(memories=memories)


@router.post("", response_model=AgentMemory, status_code=status.HTTP_201_CREATED)
async def upsert_memory(
    request: MemoryUpsertRequest,
    context: PermissionContext = Depends(get_permission_context),
) -> AgentMemory:
    """Create or update one memory for the current user.

    为当前用户创建或更新一条记忆。
    """

    return await MemoryService().upsert_from_request(
        context=context,
        request=request,
    )


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    context: PermissionContext = Depends(get_permission_context),
) -> None:
    """Delete one memory owned by the current user.

    删除当前用户拥有的一条记忆。
    """

    deleted = await MemoryService().delete_memory(
        context=context,
        memory_id=memory_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found.")
