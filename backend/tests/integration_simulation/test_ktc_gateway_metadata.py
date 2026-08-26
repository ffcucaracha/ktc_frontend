from copy import deepcopy

from app.core.config import Settings
from app.integrations.simulation.ktc_gateway import KtcOilHeatingGateway


def status_payload() -> dict[str, object]:
    return {
        "valves": {
            "KR1": False,
            "KR2": False,
            "KR3": False,
            "KR4": False,
            "KR5": False,
            "KR6": False,
        },
        "pumps": {"H1A": False, "H1B": False, "H1C": False, "ND1": False},
        "sensors_in": {
            "QR1": 0.850,
            "TR1": 20.0,
        },
        "flow_meters": {
            "FQR117_1": 10.0,
            "FQR117_2": 0.0,
            "FQR117_3": 12.0,
        },
        "collector": {
            "TR1_collector": 95.0,
            "PRA1": 1.2,
        },
        "regulators": {"FRC404": 0, "FRC405": 0, "FRC406": 0},
        "output": {"TR2": 95.0, "oil_flow_exit": 0.0, "KR6": False},
        "dosing": {"ND1_flow": 0.0, "ND1_target": 0.0, "ND1_error": False},
        "errors": {
            "process_stopped": False,
            "stop_reason": "",
            "KR6_error": False,
            "overheat_error": False,
            "pump_broken": {"H1A": False, "H1B": False, "H1C": False},
        },
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
    output = changed_payload["output"]
    assert isinstance(output, dict)
    output["TR2"] = 96.5
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
