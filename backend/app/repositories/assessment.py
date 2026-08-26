from collections.abc import Iterable
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
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
        now = utc_now()
        statement = insert(TrainingResult).values(
            id=uuid4(),
            session_id=session_id,
            scenario_id=scenario_id,
            score=score,
            max_score=max_score,
            reaction_time_ms=reaction_time_ms,
            error_count=error_count,
            critical_error_count=critical_error_count,
            sequence_score=sequence_score,
            reaction_score=reaction_score,
            safety_score=safety_score,
            status=status,
            summary=summary,
            created_at=now,
            updated_at=now,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[TrainingResult.session_id],
            set_={
                "scenario_id": statement.excluded.scenario_id,
                "score": statement.excluded.score,
                "max_score": statement.excluded.max_score,
                "reaction_time_ms": statement.excluded.reaction_time_ms,
                "error_count": statement.excluded.error_count,
                "critical_error_count": statement.excluded.critical_error_count,
                "sequence_score": statement.excluded.sequence_score,
                "reaction_score": statement.excluded.reaction_score,
                "safety_score": statement.excluded.safety_score,
                "status": statement.excluded.status,
                "summary": statement.excluded.summary,
                "updated_at": now,
            },
        ).returning(TrainingResult)

        result = await self._session.execute(statement)
        return result.scalar_one()
