"""SQL guardrail boundary for validating generated or user-provided SQL.

用于校验模型生成或用户提供 SQL 的安全护栏边界。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SQLGuardResult:
    """Describe whether SQL is allowed and any optional rewritten statement.

    描述 SQL 是否允许执行，以及可选的改写后语句。
    """

    allowed: bool
    reason: str | None = None
    rewritten_sql: str | None = None


class SQLGuard:
    """Reject obvious write operations before SQL reaches a data source.

    在 SQL 到达数据源之前拒绝明显的写操作。
    """

    def validate(self, sql: str) -> SQLGuardResult:
        """Perform a lightweight read-only validation of one SQL statement.

        对一条 SQL 语句执行轻量级只读校验。
        """

        normalized = sql.strip().lower()
        if not normalized.startswith("select"):
            return SQLGuardResult(allowed=False, reason="Only SELECT statements are allowed")
        blocked = [" drop ", " delete ", " update ", " insert ", " alter ", " truncate "]
        if any(token in f" {normalized} " for token in blocked):
            return SQLGuardResult(allowed=False, reason="Statement contains blocked SQL keyword")
        return SQLGuardResult(allowed=True, rewritten_sql=sql)
