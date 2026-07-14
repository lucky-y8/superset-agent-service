"""Deterministic evaluation service for persisted Agent runs.

针对已持久化 Agent 运行的确定性自动评估服务。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from superset_agent_service.db.session import AsyncSessionLocal
from superset_agent_service.evaluations.models import (
    EvaluationCaseModel,
    EvaluationResultModel,
)
from superset_agent_service.evaluations.schemas import (
    EvaluationCase,
    EvaluationCaseCreate,
    EvaluationResult,
)
from superset_agent_service.runs.models import AgentRunModel

SessionFactory = async_sessionmaker[AsyncSession]


class EvaluationService:
    """Manage evaluation cases and score runs without another LLM call.

    管理评估用例，并且无需再次调用大模型即可对运行结果评分。
    """

    def __init__(self, session_factory: SessionFactory = AsyncSessionLocal) -> None:
        self.session_factory = session_factory

    async def create_case(
        self, payload: EvaluationCaseCreate, created_by: str
    ) -> EvaluationCase:
        """Persist a reusable evaluation case.

        持久化一个可重复使用的评估用例。
        """

        model = EvaluationCaseModel(created_by=created_by, **payload.model_dump())
        async with self.session_factory() as session:
            session.add(model)
            await session.commit()
            await session.refresh(model)
        return self._case_schema(model)

    async def list_cases(self, enabled_only: bool = False) -> list[EvaluationCase]:
        """Return evaluation cases in creation order.

        按创建时间返回评估用例。
        """

        statement = select(EvaluationCaseModel).order_by(EvaluationCaseModel.created_at)
        if enabled_only:
            statement = statement.where(EvaluationCaseModel.enabled.is_(True))
        async with self.session_factory() as session:
            models = (await session.scalars(statement)).all()
        return [self._case_schema(model) for model in models]

    async def get_case(self, case_id: str) -> EvaluationCase | None:
        """Load one evaluation case for execution or inspection.

        加载一个评估用例，供自动执行或详情查看使用。
        """

        async with self.session_factory() as session:
            model = await session.get(EvaluationCaseModel, case_id)
        return self._case_schema(model) if model is not None else None

    async def evaluate_run(
        self, case_id: str, run_id: str, evaluated_by: str
    ) -> EvaluationResult:
        """Score answer text and observed tool calls against one case.

        根据用例规则，对答案文本和实际工具调用进行自动评分。
        """

        async with self.session_factory() as session:
            case = await session.get(EvaluationCaseModel, case_id)
            if case is None:
                raise LookupError("Evaluation case not found")

            run = await session.scalar(
                select(AgentRunModel)
                .options(selectinload(AgentRunModel.events))
                .where(AgentRunModel.run_id == run_id)
            )
            if run is None:
                raise LookupError("Agent run not found")

            answer = run.final_answer or ""
            observed_tools = self._observed_tools(run)
            answer_score, matched_terms, missing_terms = self._answer_score(
                answer, case.expected_answer_contains
            )
            tool_score, matched_tools, missing_tools = self._tool_score(
                observed_tools, case.expected_tools
            )
            forbidden_hits = [
                term
                for term in case.forbidden_answer_contains
                if term.casefold() in answer.casefold()
            ]

            score = self._weighted_score(
                answer_score,
                tool_score,
                has_answer_rules=bool(case.expected_answer_contains),
                has_tool_rules=bool(case.expected_tools),
            )
            if run.status != "completed" or forbidden_hits:
                score = 0.0
            score = round(score, 4)
            status = "passed" if score >= case.minimum_score else "failed"
            details = {
                "run_status": run.status,
                "minimum_score": case.minimum_score,
                "matched_answer_terms": matched_terms,
                "missing_answer_terms": missing_terms,
                "matched_tools": matched_tools,
                "missing_tools": missing_tools,
                "observed_tools": sorted(observed_tools),
                "forbidden_hits": forbidden_hits,
            }
            result = EvaluationResultModel(
                case_id=case_id,
                run_id=run_id,
                status=status,
                score=score,
                answer_score=round(answer_score, 4),
                tool_score=round(tool_score, 4),
                details=details,
                evaluated_by=evaluated_by,
            )
            session.add(result)
            await session.commit()
            await session.refresh(result)
        return self._result_schema(result)

    async def list_results(
        self, case_id: str | None = None, limit: int = 100
    ) -> list[EvaluationResult]:
        """Return recent evaluation results for analysis and dashboards.

        返回最近的评估结果，供分析与看板展示使用。
        """

        statement = select(EvaluationResultModel).order_by(
            EvaluationResultModel.evaluated_at.desc()
        )
        if case_id:
            statement = statement.where(EvaluationResultModel.case_id == case_id)
        statement = statement.limit(limit)
        async with self.session_factory() as session:
            models = (await session.scalars(statement)).all()
        return [self._result_schema(model) for model in models]

    @staticmethod
    def _observed_tools(run: AgentRunModel) -> set[str]:
        """Extract successful or attempted MCP tool names from Run Trace.

        从 Run Trace 中提取已经尝试或成功执行的 MCP 工具名称。
        """

        names: set[str] = set()
        for event in run.events:
            if event.event_type not in {"tool_started", "tool_completed", "tool_failed"}:
                continue
            value = event.payload.get("tool") or event.payload.get("name")
            if isinstance(value, str) and value:
                names.add(value)
        return names

    @staticmethod
    def _answer_score(answer: str, expected: list[str]) -> tuple[float, list[str], list[str]]:
        """Calculate the proportion of required answer terms that appear.

        计算答案中实际出现的必需关键词比例。
        """

        if not expected:
            return 1.0, [], []
        folded = answer.casefold()
        matched = [term for term in expected if term.casefold() in folded]
        missing = [term for term in expected if term not in matched]
        return len(matched) / len(expected), matched, missing

    @staticmethod
    def _tool_score(observed: set[str], expected: list[str]) -> tuple[float, list[str], list[str]]:
        """Calculate the proportion of expected tools observed in the trace.

        计算 Run Trace 中实际出现的期望工具比例。
        """

        if not expected:
            return 1.0, [], []
        matched = [name for name in expected if name in observed]
        missing = [name for name in expected if name not in observed]
        return len(matched) / len(expected), matched, missing

    @staticmethod
    def _weighted_score(
        answer_score: float,
        tool_score: float,
        has_answer_rules: bool,
        has_tool_rules: bool,
    ) -> float:
        """Combine active score dimensions without penalizing omitted rules.

        仅组合用例中实际启用的评分维度，未配置的维度不会造成扣分。
        """

        if has_answer_rules and has_tool_rules:
            return answer_score * 0.6 + tool_score * 0.4
        if has_answer_rules:
            return answer_score
        if has_tool_rules:
            return tool_score
        return 1.0

    @staticmethod
    def _case_schema(model: EvaluationCaseModel) -> EvaluationCase:
        return EvaluationCase.model_validate(model, from_attributes=True)

    @staticmethod
    def _result_schema(model: EvaluationResultModel) -> EvaluationResult:
        return EvaluationResult.model_validate(model, from_attributes=True)
