"""SQL guardrail boundary for validating generated or user-provided SQL.

用于校验模型生成或用户提供 SQL 的安全护栏边界。
"""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from superset_agent_service.config import settings


FORBIDDEN_EXPRESSIONS = (
    exp.Alter,
    exp.Command,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Into,
    exp.Merge,
    exp.Update,
)


@dataclass(frozen=True)
class SQLGuardResult:
    """Describe whether SQL is allowed and any optional rewritten statement.

    描述 SQL 是否允许执行，以及可选的改写后语句。
    """

    allowed: bool
    reason: str | None = None
    rewritten_sql: str | None = None


class SQLGuard:
    """Validate read-only SQL structurally and enforce a maximum row count.

    从语法结构上校验只读 SQL，并强制限制最大返回行数。
    """

    def __init__(self, max_rows: int = settings.MAX_SQL_ROWS) -> None:
        """Configure the largest result set that a query may request.

        配置查询允许请求的最大结果集行数。
        """

        if max_rows < 1:
            raise ValueError("max_rows must be greater than zero")
        self.max_rows = max_rows

    def validate(self, sql: str) -> SQLGuardResult:
        """Parse one statement, reject writes, and add or clamp ``LIMIT``.

        解析单条语句、拒绝写操作，并添加或收紧 ``LIMIT``。
        """

        if not sql.strip():
            return SQLGuardResult(allowed=False, reason="SQL statement is empty")

        try:
            statements = sqlglot.parse(sql)
        except sqlglot.errors.ParseError as exc:
            return SQLGuardResult(
                allowed=False,
                reason=f"SQL could not be parsed: {exc}",
            )

        if len(statements) != 1:
            return SQLGuardResult(
                allowed=False,
                reason="Exactly one SQL statement is allowed",
            )

        statement = statements[0]
        if not isinstance(statement, exp.Query):
            return SQLGuardResult(
                allowed=False,
                reason="Only read-only query statements are allowed",
            )

        forbidden = next(
            (
                node
                for node in statement.walk()
                if isinstance(node, FORBIDDEN_EXPRESSIONS)
            ),
            None,
        )
        if forbidden is not None:
            return SQLGuardResult(
                allowed=False,
                reason=f"Statement contains forbidden operation: {forbidden.key.upper()}",
            )

        limit = statement.args.get("limit")
        if limit is None:
            statement = statement.limit(self.max_rows)
        else:
            limit_expression = limit.expression
            if not isinstance(limit_expression, exp.Literal) or not limit_expression.is_int:
                return SQLGuardResult(
                    allowed=False,
                    reason="LIMIT must be a fixed integer",
                )
            if int(limit_expression.this) > self.max_rows:
                statement = statement.limit(self.max_rows, copy=False)

        return SQLGuardResult(
            allowed=True,
            rewritten_sql=statement.sql(),
        )
