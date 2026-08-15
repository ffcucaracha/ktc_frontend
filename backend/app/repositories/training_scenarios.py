from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScenarioExpectedAction, TrainingScenario


class TrainingScenarioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_for_simulator(self, simulator_id: UUID) -> list[TrainingScenario]:
        result = await self._session.execute(
            select(TrainingScenario)
            .where(
                TrainingScenario.simulator_definition_id == simulator_id,
                TrainingScenario.is_active.is_(True),
            )
            .order_by(TrainingScenario.name.asc(), TrainingScenario.id.asc())
        )
        return list(result.scalars())

    async def get_active_for_simulator(
        self,
        scenario_id: UUID,
        simulator_id: UUID,
    ) -> TrainingScenario | None:
        result = await self._session.execute(
            select(TrainingScenario).where(
                TrainingScenario.id == scenario_id,
                TrainingScenario.simulator_definition_id == simulator_id,
                TrainingScenario.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> TrainingScenario | None:
        result = await self._session.execute(
            select(TrainingScenario).where(TrainingScenario.code == code)
        )
        return result.scalar_one_or_none()

    async def list_expected_actions(self, scenario_id: UUID) -> list[ScenarioExpectedAction]:
        result = await self._session.execute(
            select(ScenarioExpectedAction)
            .where(ScenarioExpectedAction.scenario_id == scenario_id)
            .order_by(ScenarioExpectedAction.order_index.asc())
        )
        return list(result.scalars())
