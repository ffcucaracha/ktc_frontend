from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperatorError, SimulationSession, TrainingResult


class AssessmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_errors(
        self,
        session_id: UUID,
        errors: Iterable[OperatorError],
    ) -> list[OperatorError]:
        await self._session.execute(
            delete(OperatorError).where(OperatorError.session_id == session_id)
        )
        items = list(errors)
        self._session.add_all(items)
        await self._session.flush()
        return items

    async def list_errors(self, session_id: UUID) -> list[OperatorError]:
        result = await self._session.execute(
            select(OperatorError)
            .where(OperatorError.session_id == session_id)
            .order_by(
                OperatorError.occurred_at_ms.asc().nullslast(),
                OperatorError.created_at.asc(),
            )
        )
        return list(result.scalars())

    async def list_errors_for_operator(self, operator_id: UUID) -> list[OperatorError]:
        result = await self._session.execute(
            select(OperatorError)
            .join(SimulationSession, SimulationSession.id == OperatorError.session_id)
            .where(SimulationSession.operator_id == operator_id)
            .order_by(OperatorError.created_at.asc(), OperatorError.id.asc())
        )
        return list(result.scalars())

    async def get_result(self, session_id: UUID) -> TrainingResult | None:
        result = await self._session.execute(
            select(TrainingResult).where(TrainingResult.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def list_results_for_operator(self, operator_id: UUID) -> list[TrainingResult]:
        result = await self._session.execute(
            select(TrainingResult)
            .join(SimulationSession, SimulationSession.id == TrainingResult.session_id)
            .where(SimulationSession.operator_id == operator_id)
            .order_by(TrainingResult.updated_at.desc(), TrainingResult.id.desc())
        )
        return list(result.scalars())

    async def upsert_result(
        self,
        *,
        session_id: UUID,
        scenario_id: UUID,
        score: float,
        max_score: float,
        reaction_time_ms: int | None,
        error_count: int,
        critical_error_count: int,
        sequence_score: float,
        reaction_score: float,
        safety_score: float,
        status: str,
        summary: dict[str, object],
    ) -> TrainingResult:
        result = await self.get_result(session_id)
        if result is None:
            result = TrainingResult(session_id=session_id, scenario_id=scenario_id)
            self._session.add(result)
        result.scenario_id = scenario_id
        result.score = score
        result.max_score = max_score
        result.reaction_time_ms = reaction_time_ms
        result.error_count = error_count
        result.critical_error_count = critical_error_count
        result.sequence_score = sequence_score
        result.reaction_score = reaction_score
        result.safety_score = safety_score
        result.status = status
        result.summary = summary
        await self._session.flush()
        return result
