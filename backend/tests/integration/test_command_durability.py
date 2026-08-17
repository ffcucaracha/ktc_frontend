from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.simulation.dto import CommandResult
from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.models import (
    SimulationCommand,
    SimulationCommandStatus,
    SimulationEvent,
    SimulationTimelineEventType,
    SimulatorDefinition,
    User,
    UserRole,
)
from app.security.passwords import hash_password
from app.services.simulation import SimulationService


class InspectingGateway(MockSimulationGateway):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__()
        self._session_factory = session_factory
        self.observed_pending_command = False
        self.observed_operator_event = False

    async def send_command(
        self,
        external_session_id: str,
        command_id: UUID,
        equipment_id: str,
        action: str,
        payload: dict[str, object],
        expected_revision: int | None,
    ) -> CommandResult:
        async with self._session_factory() as session:
            command = await session.scalar(
                select(SimulationCommand).where(SimulationCommand.command_id == command_id)
            )
            events = (
                await session.execute(
                    select(SimulationEvent).where(
                        SimulationEvent.event_type
                        == SimulationTimelineEventType.OPERATOR_COMMAND,
                    )
                )
            ).scalars()
            self.observed_pending_command = (
                command is not None and command.status == SimulationCommandStatus.PENDING
            )
            self.observed_operator_event = any(
                event.payload.get("command_id") == str(command_id) for event in events
            )

        return await super().send_command(
            external_session_id=external_session_id,
            command_id=command_id,
            equipment_id=equipment_id,
            action=action,
            payload=payload,
            expected_revision=expected_revision,
        )


@pytest.mark.asyncio
async def test_command_and_intent_event_are_committed_before_external_gateway_response(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with postgres_session_factory() as session:
        operator = User(
            username=f"durability-{uuid4()}",
            full_name="Durability Operator",
            role=UserRole.OPERATOR,
            password_hash=hash_password("secret-password"),
            is_active=True,
        )
        simulator = SimulatorDefinition(
            code=f"durability-simulator-{uuid4()}",
            external_id="boiler-001",
            name="Durability simulator",
            description="Command durability test",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add_all([operator, simulator])
        await session.commit()

        gateway = InspectingGateway(postgres_session_factory)
        service = SimulationService(session, gateway)
        simulation_session = await service.create_session(operator.id, simulator.id)
        outcome = await service.send_command(
            session_id=simulation_session.id,
            operator_id=operator.id,
            command_id=uuid4(),
            equipment_id="steam_supply_pump",
            action="start",
            payload={},
            expected_revision=1,
        )

    assert gateway.observed_pending_command is True
    assert gateway.observed_operator_event is True
    assert outcome.command.status == SimulationCommandStatus.ACCEPTED
