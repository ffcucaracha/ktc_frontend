from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.integrations.simulation.base import SimulationGateway
from app.integrations.simulation.dto import CommandStatus, SimulationEvent, SimulationEventType
from app.integrations.simulation.errors import SimulationIntegrationError
from app.models import (
    SimulationCommand,
    SimulationCommandStatus,
    SimulationSession,
    SimulationSessionStatus,
    SimulatorDefinition,
)
from app.repositories.simulation_sessions import (
    SimulationCommandRepository,
    SimulationSessionRepository,
    SimulatorCatalogRepository,
)

STEAM_SUPPLY_PUMP = "steam_supply_pump"
STEAM_EXHAUST_PUMP = "steam_exhaust_pump"
KTC_PUMP_H1A = "H1A"
KTC_PUMP_H1B = "H1B"
KTC_PUMP_H1V = "H1V"
COMMAND_WHITELIST = {
    STEAM_SUPPLY_PUMP: {"start", "stop"},
    STEAM_EXHAUST_PUMP: {"start", "stop"},
    KTC_PUMP_H1A: {"start", "stop"},
    KTC_PUMP_H1B: {"start", "stop"},
    KTC_PUMP_H1V: {"start", "stop"},
}


class SimulatorNotFoundError(Exception):
    pass


class SimulationSessionNotFoundError(Exception):
    pass


class InvalidSessionOperationError(Exception):
    pass


class InvalidCommandError(Exception):
    pass


class DuplicateCommandError(Exception):
    pass


class StaleStateRevisionError(Exception):
    pass


@dataclass(frozen=True)
class CommandOutcome:
    command: SimulationCommand
    integration_error: SimulationIntegrationError | None = None


class SimulationService:
    def __init__(self, session: AsyncSession, gateway: SimulationGateway) -> None:
        self._session = session
        self._gateway = gateway
        self._catalog = SimulatorCatalogRepository(session)
        self._sessions = SimulationSessionRepository(session)
        self._commands = SimulationCommandRepository(session)

    async def list_simulators(self) -> list[SimulatorDefinition]:
        return await self._catalog.list_active()

    async def get_simulator(self, simulator_id: UUID) -> SimulatorDefinition:
        simulator = await self._catalog.get_active(simulator_id)
        if simulator is None:
            raise SimulatorNotFoundError
        return simulator

    async def create_session(self, operator_id: UUID, simulator_id: UUID) -> SimulationSession:
        simulator = await self.get_simulator(simulator_id)
        local_session = await self._sessions.create(
            operator_id=operator_id,
            simulator_definition_id=simulator.id,
        )
        await self._session.commit()

        try:
            external_session = await self._gateway.create_session(
                simulator_id=simulator.external_id,
                operator_id=operator_id,
                local_session_id=local_session.id,
            )
        except SimulationIntegrationError as exc:
            local_session.status = SimulationSessionStatus.FAILED
            local_session.error_code = exc.code.value
            local_session.error_message = "Ошибка сервиса моделирования"
            await self._session.commit()
            return local_session

        local_session.external_session_id = external_session.session_id
        local_session.status = SimulationSessionStatus.ACTIVE
        local_session.started_at = utc_now()
        if external_session.state is not None:
            self._update_last_state(local_session, external_session.state.model_dump(mode="json"))
        await self._session.commit()
        return local_session

    async def get_session(self, session_id: UUID, operator_id: UUID) -> SimulationSession:
        simulation_session = await self._sessions.get_for_operator(session_id, operator_id)
        if simulation_session is None:
            raise SimulationSessionNotFoundError
        return simulation_session

    async def get_state(self, session_id: UUID, operator_id: UUID) -> dict[str, object]:
        simulation_session = await self.get_session(session_id, operator_id)
        self._ensure_active_for_operation(simulation_session)
        if simulation_session.external_session_id is None:
            raise InvalidSessionOperationError
        state = await self._gateway.get_state(simulation_session.external_session_id)
        state_payload = state.model_dump(mode="json")
        self._update_last_state(simulation_session, state_payload)
        await self._session.commit()
        return simulation_session.last_state or state_payload

    async def send_command(
        self,
        session_id: UUID,
        operator_id: UUID,
        command_id: UUID,
        equipment_id: str,
        action: str,
        payload: dict[str, object],
        expected_revision: int | None,
    ) -> CommandOutcome:
        simulation_session = await self.get_session(session_id, operator_id)
        self._ensure_active_for_operation(simulation_session)
        if simulation_session.external_session_id is None:
            raise InvalidSessionOperationError
        if action not in COMMAND_WHITELIST.get(equipment_id, set()):
            raise InvalidCommandError
        if await self._commands.get_by_command_id(command_id) is not None:
            raise DuplicateCommandError

        try:
            command = await self._commands.create_pending(
                session_id=simulation_session.id,
                command_id=command_id,
                equipment_id=equipment_id,
                action=action,
                payload=payload,
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateCommandError from exc

        try:
            result = await self._gateway.send_command(
                external_session_id=simulation_session.external_session_id,
                command_id=command_id,
                equipment_id=equipment_id,
                action=action,
                payload=payload,
                expected_revision=expected_revision,
            )
        except SimulationIntegrationError as exc:
            command.status = SimulationCommandStatus.FAILED
            command.external_error_code = exc.code.value
            command.external_error_message = "Ошибка сервиса моделирования"
            command.completed_at = utc_now()
            await self._session.commit()
            return CommandOutcome(command=command, integration_error=exc)

        if result.status == CommandStatus.ACCEPTED:
            command.status = SimulationCommandStatus.ACCEPTED
        else:
            command.status = SimulationCommandStatus.REJECTED
            command.external_error_code = result.code
            command.external_error_message = result.message
        command.completed_at = utc_now()
        await self._session.commit()
        return CommandOutcome(command=command)

    async def stop_session(self, session_id: UUID, operator_id: UUID) -> SimulationSession:
        simulation_session = await self.get_session(session_id, operator_id)
        if simulation_session.status in {
            SimulationSessionStatus.COMPLETED,
            SimulationSessionStatus.FAILED,
        }:
            return simulation_session
        if simulation_session.external_session_id is None:
            raise InvalidSessionOperationError

        simulation_session.status = SimulationSessionStatus.STOPPING
        await self._session.commit()
        try:
            await self._gateway.stop_session(simulation_session.external_session_id)
        except SimulationIntegrationError as exc:
            simulation_session.status = SimulationSessionStatus.FAILED
            simulation_session.error_code = exc.code.value
            simulation_session.error_message = "Ошибка сервиса моделирования"
            await self._session.commit()
            return simulation_session

        simulation_session.status = SimulationSessionStatus.COMPLETED
        simulation_session.ended_at = utc_now()
        await self._session.commit()
        return simulation_session

    async def apply_event(
        self, session_id: UUID, operator_id: UUID, event: SimulationEvent
    ) -> None:
        simulation_session = await self.get_session(session_id, operator_id)
        if event.type in {SimulationEventType.STATE_SNAPSHOT, SimulationEventType.STATE_PATCH}:
            self._update_last_state(simulation_session, event.data)
        elif event.type == SimulationEventType.SESSION_COMPLETED:
            simulation_session.status = SimulationSessionStatus.COMPLETED
            simulation_session.ended_at = utc_now()
        elif event.type == SimulationEventType.SESSION_FAILED:
            simulation_session.status = SimulationSessionStatus.FAILED
            simulation_session.error_code = "SESSION_FAILED"
            simulation_session.error_message = "Сессия моделирования завершилась ошибкой"
        await self._session.commit()

    @staticmethod
    def _ensure_active_for_operation(simulation_session: SimulationSession) -> None:
        if simulation_session.status != SimulationSessionStatus.ACTIVE:
            raise InvalidSessionOperationError

    @staticmethod
    def _update_last_state(
        simulation_session: SimulationSession,
        new_state: dict[str, object],
    ) -> None:
        new_revision = new_state.get("revision")
        if not isinstance(new_revision, int):
            raise StaleStateRevisionError
        current_revision = None
        if simulation_session.last_state is not None:
            current_revision = simulation_session.last_state.get("revision")
        if isinstance(current_revision, int) and new_revision < current_revision:
            raise StaleStateRevisionError
        simulation_session.last_state = new_state
