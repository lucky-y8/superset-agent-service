"""SQL guardrail boundary for validating generated or user-provided SQL."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SQLGuardResult:
    allowed: bool
    reason: str | None = None
    rewritten_sql: str | None = None


class SQLGuard:
    def validate(self, sql: str) -> SQLGuardResult:
        normalized = sql.strip().lower()
        if not normalized.startswith("select"):
            return SQLGuardResult(allowed=False, reason="Only SELECT statements are allowed")
        blocked = [" drop ", " delete ", " update ", " insert ", " alter ", " truncate "]
        if any(token in f" {normalized} " for token in blocked):
            return SQLGuardResult(allowed=False, reason="Statement contains blocked SQL keyword")
        return SQLGuardResult(allowed=True, rewritten_sql=sql)
