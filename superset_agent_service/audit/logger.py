"""Audit logging boundary for security and compliance events.

记录安全与合规事件的审计日志边界。
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from superset_agent_service.audit.models import AgentAuditLogModel
from superset_agent_service.auth.schemas import PermissionContext
from superset_agent_service.db.session import AsyncSessionLocal

logger = logging.getLogger("superset_agent_service.audit")
SessionFactory = async_sessionmaker[AsyncSession]


class AuditLogger:
    """Persist structured audit facts and mirror them to structured logs.

    持久化结构化审计事实，并同步输出结构化日志。
    """

    def __init__(self, session_factory: SessionFactory = AsyncSessionLocal) -> None:
        """Create an audit logger bound to the configured database.

        创建绑定到当前数据库的审计日志记录器。
        """

        self.session_factory = session_factory

    async def record(
        self,
        user_id: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
        username: str | None = None,
        tenant_id: str | None = None,
        outcome: str = "success",
    ) -> None:
        """Record who performed an action on which optional resource.

        记录谁对哪个可选资源执行了什么操作。
        """

        async with self.session_factory() as session:
            session.add(
                AgentAuditLogModel(
                    run_id=run_id,
                    user_id=user_id,
                    username=username,
                    tenant_id=tenant_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    outcome=outcome,
                    event_metadata=metadata or {},
                )
            )
            await session.commit()

        logger.info(
            "audit run=%s user=%s username=%s action=%s resource_type=%s resource_id=%s outcome=%s metadata=%s",
            run_id,
            user_id,
            username,
            action,
            resource_type,
            resource_id,
            outcome,
            metadata or {},
        )

    async def record_context(
        self,
        context: PermissionContext,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
        outcome: str = "success",
    ) -> None:
        """Record an event using the authenticated request context.

        使用已认证的请求上下文记录审计事件。
        """

        await self.record(
            run_id=run_id,
            user_id=context.user_id,
            username=context.username,
            tenant_id=context.tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            metadata=metadata,
        )
