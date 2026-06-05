"""Audit logging boundary for security and compliance events."""

import logging

logger = logging.getLogger("superset_agent_service.audit")


class AuditLogger:
    async def record(
        self,
        user_id: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        logger.info(
            "audit user=%s action=%s resource_type=%s resource_id=%s metadata=%s",
            user_id,
            action,
            resource_type,
            resource_id,
            metadata or {},
        )
