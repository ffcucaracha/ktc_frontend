from copy import deepcopy

from app.core.config import Settings
from app.integrations.simulation.ktc_gateway import KtcOilHeatingGateway


def status_payload() -> dict[str, object]:
    return {
        "pumps": {"H1A": False, "H1B": False, "H1V": False},
        "sensors": {
            "QR5K3D": 850.0,
            "FQR117_1": 10.0,
            "FQR117_2": 12.0,
            "TR41_1": 95.0,
            "PRA351": 1.2,
        },
        "regulators": {"FRC404": 0, "FRC405": 0, "FRC406": 0},
        "installation_output": {},
    }


def gateway() -> KtcOilHeatingGateway:
    return KtcOilHeatingGateway(Settings())


def test_uses_ktc_backend_revision_and_simulation_time_when_present() -> None:
    payload = status_payload()
    payload["revision"] = 42
    payload["simulation_time_ms"] = 18_750

    state = gateway()._map_status(payload)

    assert state.revision == 42
    assert state.simulation_time_ms == 18_750
    assert state.process is not None
    metadata = state.process["timeline_metadata"]
    assert isinstance(metadata, dict)
    assert metadata["revision_source"] == "ktc_backend"
    assert metadata["simulation_time_source"] == "ktc_backend"


def test_fallback_revision_advances_when_dynamic_payload_changes() -> None:
    ktc_gateway = gateway()
    first_payload = status_payload()
    first = ktc_gateway._map_status(first_payload)
    same = ktc_gateway._map_status(deepcopy(first_payload))

    changed_payload = deepcopy(first_payload)
    sensors = changed_payload["sensors"]
    assert isinstance(sensors, dict)
    sensors["TR41_1"] = 96.5
    changed = ktc_gateway._map_status(changed_payload)

    assert same.revision == first.revision
    assert changed.revision == first.revision + 1
    assert changed.simulation_time_ms == changed.revision * 1_000


def test_preserves_extended_ktc_payload_for_future_telemetry_and_ai() -> None:
    payload = status_payload()
    payload["new_process_block"] = {
        "heat_exchanger_efficiency": 0.91,
        "dynamic_parameter": 123.4,
    }

    state = gateway()._map_status(payload)

    assert state.process is not None
    raw = state.process["raw"]
    assert isinstance(raw, dict)
    assert raw["new_process_block"] == payload["new_process_block"]
