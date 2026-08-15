from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.models import SimulationEvent, SimulatorDefinition, User, UserRole
from app.security.passwords import hash_password
from app.services.simulation import SimulationService


@pytest.mark.asyncio
async def test_simulation_service_records_complete_timeline(
    postgres_session_factory: async_sessionmaker,
) -> None:
    async with postgres_session_factory() as session:
        operator = User(
            username=f"timeline-{uuid4()}",
            full_name="Timeline Operator",
            role=UserRole.OPERATOR,
            password_hash=hash_password("secret-password"),
            is_active=True,
        )
        simulator = SimulatorDefinition(
            code=f"timeline-{uuid4()}",
            external_id="boiler-001",
            name="Timeline simulator",
            description="Timeline test",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add_all([operator, simulator])
        await session.commit()

        service = SimulationService(session, MockSimulationGateway())
        simulation_session = await service.create_session(operator.id, simulator.id)

        # Repeated reads of revision 1 must not duplicate state.snapshot.
        await service.get_state(simulation_session.id, operator.id)
        await service.get_state(simulation_session.id, operator.id)

        command_id = uuid4()
        outcome = await service.send_command(
            session_id=simulation_session.id,
            operator_id=operator.id,
            command_id=command_id,
            equipment_id="steam_supply_pump",
            action="start",
            payload={},
            expected_revision=1,
        )
        assert outcome.command.status == "accepted"

        # Persist the state produced by the command as revision 2.
        await service.get_state(simulation_session.id, operator.id)
        await service.stop_session(simulation_session.id, operator.id)

        result = await session.execute(
            select(SimulationEvent)
            .where(SimulationEvent.session_id == simulation_session.id)
            .order_by(SimulationEvent.created_at.asc(), SimulationEvent.id.asc())
        )
        events = list(result.scalars())

    event_types = [event.event_type for event in events]
    assert event_types.count("session.started") == 1
    assert event_types.count("state.snapshot") == 2
    assert event_types.count("operator.command") == 1
    assert event_types.count("command.accepted") == 1
    assert event_types.count("session.completed") == 1

    snapshots = [event for event in events if event.event_type == "state.snapshot"]
    assert [event.revision for event in snapshots] == [1, 2]

    operator_event = next(event for event in events if event.event_type == "operator.command")
    assert operator_event.source == "operator"
    assert operator_event.payload["command_id"] == str(command_id)
    assert operator_event.payload["equipment_id"] == "steam_supply_pump"
    assert operator_event.payload["expected_revision"] == 1
