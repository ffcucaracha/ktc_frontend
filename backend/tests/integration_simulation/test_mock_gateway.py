from uuid import uuid4

import pytest

from app.integrations.simulation.dto import CommandStatus, EquipmentStatus, SimulationEventType
from app.integrations.simulation.errors import InvalidExternalPayloadError, SimulationTimeoutError
from app.integrations.simulation.mock_gateway import MockSimulationGateway


@pytest.mark.asyncio
async def test_mock_gateway_fixture_and_status_only_command_update() -> None:
    gateway = MockSimulationGateway()
    session = await gateway.create_session("boiler-001", uuid4(), uuid4())
    initial_state = await gateway.get_state(session.session_id)

    result = await gateway.send_command(
        external_session_id=session.session_id,
        command_id=uuid4(),
        equipment_id="steam_supply_pump",
        action="start",
        payload={},
        expected_revision=initial_state.revision,
    )
    updated_state = await gateway.get_state(session.session_id)

    assert result.status == CommandStatus.ACCEPTED
    assert updated_state.equipment["steam_supply_pump"].status == EquipmentStatus.RUNNING
    assert updated_state.boiler.temperature_c == initial_state.boiler.temperature_c
    assert updated_state.boiler.pressure_bar == initial_state.boiler.pressure_bar
    assert updated_state.equipment["steam_supply_pump"].flow_kg_h == 0


@pytest.mark.asyncio
async def test_mock_gateway_rejected_timeout_and_events() -> None:
    rejected_gateway = MockSimulationGateway(reject_commands=True)
    rejected = await rejected_gateway.send_command(
        external_session_id="mock",
        command_id=uuid4(),
        equipment_id="steam_supply_pump",
        action="start",
        payload={},
        expected_revision=1,
    )
    assert rejected.status == CommandStatus.REJECTED

    timeout_gateway = MockSimulationGateway(timeout=True)
    with pytest.raises(SimulationTimeoutError):
        await timeout_gateway.get_state("mock")

    event_gateway = MockSimulationGateway()
    events = [event async for event in event_gateway.stream_events("mock")]
    assert events[0].type == SimulationEventType.SESSION_READY
    assert events[1].type == SimulationEventType.STATE_SNAPSHOT


@pytest.mark.asyncio
async def test_mock_gateway_malformed_event() -> None:
    gateway = MockSimulationGateway(malformed_event=True)
    stream = gateway.stream_events("mock")
    first_event = await anext(stream)

    assert first_event.type == SimulationEventType.SESSION_READY
    with pytest.raises(InvalidExternalPayloadError):
        await anext(stream)
