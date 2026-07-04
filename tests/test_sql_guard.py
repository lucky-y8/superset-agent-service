"""Unit tests for the AST-based SQL safety guard.

基于 AST 的 SQL 安全护栏单元测试。
"""

import unittest

import sqlglot

from superset_agent_service.guards.sql_guard import SQLGuard


class SQLGuardTests(unittest.TestCase):
    """Verify read-only enforcement and result-size rewriting.

    验证只读限制和结果行数改写逻辑。
    """

    def setUp(self) -> None:
        """Use a small row limit so rewritten SQL is easy to inspect.

        使用较小的行数限制，便于检查改写后的 SQL。
        """

        self.guard = SQLGuard(max_rows=100)

    def test_adds_limit_to_select_without_limit(self) -> None:
        """Add the configured maximum when a query has no LIMIT.

        查询没有 LIMIT 时添加配置的最大行数。
        """

        result = self.guard.validate("SELECT id, name FROM dashboards")

        self.assertTrue(result.allowed)
        self.assertEqual(self._limit_value(result.rewritten_sql), 100)

    def test_preserves_smaller_existing_limit(self) -> None:
        """Keep an existing LIMIT that is already below the maximum.

        保留原本就小于最大值的 LIMIT。
        """

        result = self.guard.validate("SELECT * FROM dashboards LIMIT 5")

        self.assertTrue(result.allowed)
        self.assertEqual(self._limit_value(result.rewritten_sql), 5)

    def test_clamps_limit_above_maximum(self) -> None:
        """Reduce an excessive LIMIT to the configured maximum.

        将过大的 LIMIT 收紧到配置的最大值。
        """

        result = self.guard.validate("SELECT * FROM dashboards LIMIT 5000")

        self.assertTrue(result.allowed)
        self.assertEqual(self._limit_value(result.rewritten_sql), 100)

    def test_allows_common_table_expression_query(self) -> None:
        """Allow a read-only WITH query and still enforce its outer LIMIT.

        允许只读 WITH 查询，并继续限制其外层返回行数。
        """

        result = self.guard.validate(
            "WITH recent AS (SELECT id FROM dashboards) SELECT * FROM recent"
        )

        self.assertTrue(result.allowed)
        self.assertEqual(self._limit_value(result.rewritten_sql), 100)

    def test_rejects_write_statements(self) -> None:
        """Reject representative DML and DDL statements.

        拒绝典型的 DML 和 DDL 写入语句。
        """

        statements = [
            "INSERT INTO dashboards (id) VALUES (1)",
            "UPDATE dashboards SET name = 'changed'",
            "DELETE FROM dashboards",
            "DROP TABLE dashboards",
            "CREATE TABLE copied AS SELECT * FROM dashboards",
        ]

        for statement in statements:
            with self.subTest(statement=statement):
                result = self.guard.validate(statement)
                self.assertFalse(result.allowed)

    def test_rejects_multiple_statements(self) -> None:
        """Reject statement stacking even when the first query is read-only.

        即使第一条查询只读，也拒绝堆叠执行多条语句。
        """

        result = self.guard.validate("SELECT 1; DROP TABLE dashboards")

        self.assertFalse(result.allowed)
        self.assertIn("Exactly one", result.reason)

    def test_rejects_dynamic_limit(self) -> None:
        """Reject parameterized LIMIT values that cannot be bounded statically.

        拒绝无法静态确定上限的参数化 LIMIT。
        """

        result = self.guard.validate("SELECT * FROM dashboards LIMIT :row_count")

        self.assertFalse(result.allowed)
        self.assertIn("fixed integer", result.reason)

    def test_keyword_inside_string_does_not_trigger_false_positive(self) -> None:
        """Allow harmless text containing words such as DROP or DELETE.

        允许字符串中包含 DROP 或 DELETE 等无害文本。
        """

        result = self.guard.validate("SELECT 'DROP TABLE is text' AS message")

        self.assertTrue(result.allowed)

    def test_rejects_invalid_sql(self) -> None:
        """Return a validation result instead of raising a parser exception.

        返回校验结果，而不是向外抛出解析器异常。
        """

        result = self.guard.validate("SELECT FROM")

        self.assertFalse(result.allowed)
        self.assertIn("could not be parsed", result.reason)

    @staticmethod
    def _limit_value(sql: str | None) -> int:
        """Read the integer LIMIT from rewritten SQL.

        从改写后的 SQL 中读取整数 LIMIT。
        """

        assert sql is not None
        statement = sqlglot.parse_one(sql)
        return int(statement.args["limit"].expression.this)


if __name__ == "__main__":
    unittest.main()
