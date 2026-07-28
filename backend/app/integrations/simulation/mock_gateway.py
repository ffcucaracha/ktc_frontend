from collections.abc import AsyncIterator
from uuid import UUID

from app.integrations.simulation.dto import (
    AlarmSeverity,
    BoilerState,
    BoilerStatus,
    CommandResult,
    CommandStatus,
    EquipmentState,
    EquipmentStatus,
    ExternalSession,
    SimulationEvent,
    SimulationEventType,
    SimulationState,
)
from app.integrations.simulation.errors import (
    InvalidExternalPayloadError,
    SimulationSessionNotFoundError,
    SimulationTimeoutError,
)

STEAM_SUPPLY_PUMP = "steam_supply_pump"
STEAM_EXHAUST_PUMP = "steam_exhaust_pump"
SUPPORTED_EQUIPMENT = {STEAM_SUPPLY_PUMP, STEAM_EXHAUST_PUMP}
SUPPORTED_ACTIONS = {"start", "stop"}


class MockSimulationGateway:
    def __init__(
        self,
        reject_commands: bool = False,
        timeout: bool = False,
        malformed_event: bool = False,
    ) -> None:
        self._reject_commands = reject_commands
        self._timeout = timeout
        self._malformed_event = malformed_event
        self._states: dict[str, SimulationState] = {}

    async def create_session(
        self,
        simulator_id: str,
        operator_id: UUID,
        local_session_id: UUID,
    ) -> ExternalSession:
        del operator_id
        await self._maybe_timeout()
        external_session_id = f"mock-{local_session_id}"
        self._states[external_session_id] = self._initial_state()
        return ExternalSession(
            session_id=external_session_id,
            status="active",
            state=self._states[external_session_id],
        )

    async def get_state(self, external_session_id: str) -> SimulationState:
        await self._maybe_timeout()
        return self._state_for(external_session_id)

    async def send_command(
        self,
        external_session_id: str,
        command_id: UUID,
        equipment_id: str,
        action: str,
        payload: dict[str, object],
        expected_revision: int | None,
    ) -> CommandResult:
        del payload, expected_revision
        await self._maybe_timeout()
        state = self._state_for(external_session_id)

        if (
            self._reject_commands
            or equipment_id not in SUPPORTED_EQUIPMENT
            or action not in SUPPORTED_ACTIONS
        ):
            return CommandResult(
                command_id=command_id,
                status=CommandStatus.REJECTED,
                code="COMMAND_REJECTED",
                message="Команда отклонена mock gateway",
            )

        equipment = dict(state.equipment)
        current = equipment[equipment_id]
        next_status = EquipmentStatus.RUNNING if action == "start" else EquipmentStatus.STOPPED
        equipment[equipment_id] = EquipmentState(status=next_status, flow_kg_h=current.flow_kg_h)
        self._states[external_session_id] = state.model_copy(
            update={
                "revision": state.revision + 1,
                "equipment": equipment,
            },
        )
        return CommandResult(command_id=command_id, status=CommandStatus.ACCEPTED)

    async def stop_session(self, external_session_id: str) -> None:
        del external_session_id
        await self._maybe_timeout()

    async def stream_events(self, external_session_id: str) -> AsyncIterator[SimulationEvent]:
        await self._maybe_timeout()
        yield SimulationEvent(
            type=SimulationEventType.SESSION_READY,
            data={"status": "active"},
        )
        if self._malformed_event:
            raise InvalidExternalPayloadError
        yield SimulationEvent(
            type=SimulationEventType.STATE_SNAPSHOT,
            data=self._state_for(external_session_id).model_dump(mode="json"),
        )

    async def raise_prepared_alarm(self) -> SimulationEvent:
        return SimulationEvent(
            type=SimulationEventType.ALARM_RAISED,
            data={
                "code": "MOCK_ALARM",
                "severity": AlarmSeverity.WARNING.value,
                "message": "Подготовленное событие mock gateway",
                "active": True,
            },
        )

    async def _maybe_timeout(self) -> None:
        if self._timeout:
            raise SimulationTimeoutError

    def _state_for(self, external_session_id: str) -> SimulationState:
        if external_session_id == "mock":
            self._states.setdefault(external_session_id, self._initial_state())
        state = self._states.get(external_session_id)
        if state is None:
            raise SimulationSessionNotFoundError
        return state

    @staticmethod
    def _initial_state() -> SimulationState:
        return SimulationState(
            revision=1,
            simulation_time_ms=0,
            boiler=BoilerState(
                temperature_c=100.0,
                pressure_bar=1.0,
                status=BoilerStatus.IDLE,
            ),
            equipment={
                STEAM_SUPPLY_PUMP: EquipmentState(
                    status=EquipmentStatus.STOPPED,
                    flow_kg_h=0,
                ),
                STEAM_EXHAUST_PUMP: EquipmentState(
                    status=EquipmentStatus.STOPPED,
                    flow_kg_h=0,
                ),
            },
            alarms=[],
        )
