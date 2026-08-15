from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    SimulationCommand,
    SimulationCommandStatus,
    SimulationSession,
    SimulationSessionStatus,
    SimulatorDefinition,
    TrainingSessionMode,
)


class SimulatorCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[SimulatorDefinition]:
        result = await self._session.execute(
            select(SimulatorDefinition)
            .where(SimulatorDefinition.is_active.is_(True))
            .order_by(SimulatorDefinition.name.asc(), SimulatorDefinition.id.asc()),
        )
        return list(result.scalars())

    async def get_active(self, simulator_id: UUID) -> SimulatorDefinition | None:
        result = await self._session.execute(
            select(SimulatorDefinition).where(
                SimulatorDefinition.id == simulator_id,
                SimulatorDefinition.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()


class SimulationSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        operator_id: UUID,
        simulator_definition_id: UUID,
        training_scenario_id: UUID | None = None,
        mode: TrainingSessionMode = TrainingSessionMode.TRAINING,
    ) -> SimulationSession:
        simulation_session = SimulationSession(
            operator_id=operator_id,
            simulator_definition_id=simulator_definition_id,
            training_scenario_id=training_scenario_id,
            mode=mode,
            status=SimulationSessionStatus.CREATING,
        )
        self._session.add(simulation_session)
        await self._session.flush()
        return simulation_session

    async def get_for_operator(
        self,
        session_id: UUID,
        operator_id: UUID,
    ) -> SimulationSession | None:
        result = await self._session.execute(
            select(SimulationSession).where(
                SimulationSession.id == session_id,
                SimulationSession.operator_id == operator_id,
            ),
        )
        return result.scalar_one_or_none()

    async def get(self, session_id: UUID) -> SimulationSession | None:
        result = await self._session.execute(
            select(SimulationSession).where(SimulationSession.id == session_id),
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[SimulationSession]:
        result = await self._session.execute(
            select(SimulationSession)
            .where(SimulationSession.status == SimulationSessionStatus.ACTIVE)
            .order_by(SimulationSession.started_at.asc(), SimulationSession.id.asc()),
        )
        return list(result.scalars())


class SimulationCommandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending(
        self,
        session_id: UUID,
        command_id: UUID,
        equipment_id: str,
        action: str,
        payload: dict[str, object],
    ) -> SimulationCommand:
        command = SimulationCommand(
            session_id=session_id,
            command_id=command_id,
            equipment_id=equipment_id,
            action=action,
            payload=payload,
            status=SimulationCommandStatus.PENDING,
        )
        self._session.add(command)
        await self._session.flush()
        return command

    async def get_by_command_id(self, command_id: UUID) -> SimulationCommand | None:
        result = await self._session.execute(
            select(SimulationCommand).where(SimulationCommand.command_id == command_id),
        )
        return result.scalar_one_or_none()
