from uuid import UUID

from app.features.risk import extract_risk_features
from app.schemas.contracts import OperatorProfile, RecentAction, RiskPredictionRequest, TelemetryPoint


def test_extracts_time_deltas_and_uses_only_past_actions() -> None:
    request = RiskPredictionRequest(
        session_id=UUID("00000000-0000-0000-0000-000000000001"),
        scenario_code="oil-heating-basic-startup",
        operator_profile=OperatorProfile(previous_errors={"LATE_ACTION": 2}),
        window=[
            TelemetryPoint(
                simulation_time_ms=0,
                revision=1,
                sensors={"PRA351": 1.0, "TR41_1": 90.0},
                pumps={"H1A": False},
            ),
            TelemetryPoint(
                simulation_time_ms=5_000,
                revision=2,
                sensors={"PRA351": 1.5, "TR41_1": 95.0},
                pumps={"H1A": True},
            ),
            TelemetryPoint(
                simulation_time_ms=10_000,
                revision=3,
                sensors={"PRA351": 2.0, "TR41_1": 100.0},
                pumps={"H1A": True},
                regulators={"FRC404": 50},
            ),
        ],
        recent_actions=[
            RecentAction(simulation_time_ms=8_000, equipment_id="H1A", action="start"),
            RecentAction(simulation_time_ms=11_000, equipment_id="H1B", action="start"),
        ],
    )

    features = extract_risk_features(request)

    assert features["current_pressure"] == 2.0
    assert features["pressure_delta_5s"] == 0.5
    assert features["pressure_delta_10s"] == 1.0
    assert features["temperature_delta_10s"] == 10.0
    assert features["time_since_last_action_s"] == 2.0
    assert features["action_count_last_10s"] == 1.0
    assert features["scenario_step"] == 1.0
    assert features["previous_late_action_count"] == 2.0
