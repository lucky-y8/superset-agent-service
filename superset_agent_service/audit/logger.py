"""Audit logging boundary for security and compliance events.

记录安全与合规事件的审计日志边界。
"""

import logging

logger = logging.getLogger("superset_agent_service.audit")


class AuditLogger:
    """Write structured audit facts through the standard logging system.

    通过标准日志系统写入结构化审计信息。
    """

    async def record(
        self,
        user_id: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Record who performed an action on which optional resource.

        记录谁对哪个可选资源执行了什么操作。
        """

        logger.info(
            "audit user=%s action=%s resource_type=%s resource_id=%s metadata=%s",
            user_id,
            action,
            resource_type,
            resource_id,
            metadata or {},
        )
