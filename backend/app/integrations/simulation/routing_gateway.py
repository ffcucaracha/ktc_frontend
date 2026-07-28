from collections.abc import AsyncIterator
from uuid import UUID

from app.integrations.simulation.base import SimulationGateway
from app.integrations.simulation.dto import (
    CommandResult,
    ExternalSession,
    SimulationEvent,
    SimulationState,
)
from app.integrations.simulation.ktc_gateway import KTC_EXTERNAL_SESSION_PREFIX
from app.repositories.simulators import KTC_OIL_HEATING_EXTERNAL_ID


class RoutingSimulationGateway:
    def __init__(
        self,
        default_gateway: SimulationGateway,
        ktc_gateway: SimulationGateway,
    ) -> None:
        self._default_gateway = default_gateway
        self._ktc_gateway = ktc_gateway

    async def create_session(
        self,
        simulator_id: str,
        operator_id: UUID,
        local_session_id: UUID,
    ) -> ExternalSession:
        return await self._gateway_for_simulator_id(simulator_id).create_session(
            simulator_id=simulator_id,
            operator_id=operator_id,
            local_session_id=local_session_id,
        )

    async def get_state(self, external_session_id: str) -> SimulationState:
        return await self._gateway_for_external_session_id(external_session_id).get_state(
            external_session_id,
        )

    async def send_command(
        self,
        external_session_id: str,
        command_id: UUID,
        equipment_id: str,
        action: str,
        payload: dict[str, object],
        expected_revision: int | None,
    ) -> CommandResult:
        return await self._gateway_for_external_session_id(external_session_id).send_command(
            external_session_id=external_session_id,
            command_id=command_id,
            equipment_id=equipment_id,
            action=action,
            payload=payload,
            expected_revision=expected_revision,
        )

    async def stop_session(self, external_session_id: str) -> None:
        await self._gateway_for_external_session_id(external_session_id).stop_session(
            external_session_id,
        )

    def stream_events(self, external_session_id: str) -> AsyncIterator[SimulationEvent]:
        return self._gateway_for_external_session_id(external_session_id).stream_events(
            external_session_id,
        )

    def _gateway_for_simulator_id(self, simulator_id: str) -> SimulationGateway:
        if simulator_id == KTC_OIL_HEATING_EXTERNAL_ID:
            return self._ktc_gateway
        return self._default_gateway

    def _gateway_for_external_session_id(self, external_session_id: str) -> SimulationGateway:
        if external_session_id.startswith(KTC_EXTERNAL_SESSION_PREFIX):
            return self._ktc_gateway
        return self._default_gateway
