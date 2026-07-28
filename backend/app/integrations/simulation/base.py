from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from app.integrations.simulation.dto import (
    CommandResult,
    ExternalSession,
    SimulationEvent,
    SimulationState,
)


class SimulationGateway(Protocol):
    async def create_session(
        self,
        simulator_id: str,
        operator_id: UUID,
        local_session_id: UUID,
    ) -> ExternalSession: ...

    async def get_state(self, external_session_id: str) -> SimulationState: ...

    async def send_command(
        self,
        external_session_id: str,
        command_id: UUID,
        equipment_id: str,
        action: str,
        payload: dict[str, object],
        expected_revision: int | None,
    ) -> CommandResult: ...

    async def stop_session(self, external_session_id: str) -> None: ...

    def stream_events(self, external_session_id: str) -> AsyncIterator[SimulationEvent]: ...
