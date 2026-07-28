from uuid import UUID

import pytest

from app.integrations.simulation.dto import (
    CommandStatus,
    EquipmentStatus,
    SimulationEventType,
)
from app.integrations.simulation.errors import InvalidExternalPayloadError
from app.integrations.simulation.mapping import (
    parse_external_command_result,
    parse_external_event,
    parse_external_state,
)


def state_payload() -> dict[str, object]:
    return {
        "revision": 1,
        "simulation_time_ms": 0,
        "boiler": {
            "temperature_c": 100.0,
            "pressure_bar": 1.0,
            "status": "idle",
        },
        "equipment": {
            "steam_supply_pump": {"status": "stopped", "flow_kg_h": 0},
        },
        "alarms": [],
    }


def test_maps_external_state_to_internal_dto() -> None:
    state = parse_external_state(state_payload())

    assert state.revision == 1
    assert state.equipment["steam_supply_pump"].status == EquipmentStatus.STOPPED


def test_rejects_unknown_external_enum() -> None:
    payload = state_payload()
    payload["equipment"] = {
        "steam_supply_pump": {"status": "spinning-fast", "flow_kg_h": 0},
    }

    with pytest.raises(InvalidExternalPayloadError):
        parse_external_state(payload)


def test_maps_command_and_event() -> None:
    command_id = UUID("735f13c8-6700-4ad6-b86b-f5d2e8b683d3")

    command = parse_external_command_result(
        {"command_id": str(command_id), "status": "accepted"},
    )
    event = parse_external_event({"type": "session.ready", "data": {"status": "active"}})

    assert command.command_id == command_id
    assert command.status == CommandStatus.ACCEPTED
    assert event.type == SimulationEventType.SESSION_READY
