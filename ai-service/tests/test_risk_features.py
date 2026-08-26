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
                sensors={"PRA1": 1.0, "TR2": 90.0, "FQR117_1": 100.0},
                pumps={"H1A": False},
            ),
            TelemetryPoint(
                simulation_time_ms=5_000,
                revision=2,
                sensors={"PRA1": 1.5, "TR2": 95.0, "FQR117_1": 120.0},
                pumps={"H1A": True, "H1C": True, "ND1": True},
                valves={"KR1": True},
            ),
            TelemetryPoint(
                simulation_time_ms=10_000,
                revision=3,
                sensors={
                    "PRA1": 2.0,
                    "TR2": 100.0,
                    "FQR117_1": 130.0,
                    "FQR117_2": 120.0,
                    "FQR117_3": 110.0,
                },
                pumps={"H1A": True, "H1C": True, "ND1": True},
                valves={"KR1": True, "KR6": True},
                regulators={"FRC404": 50},
                dosing={"ND1_flow": 12.0, "ND1_target": 12.0},
                elou={
                    "FQR118": 300.0,
                    "FRC407_valve": 80,
                    "FRC408_valve": 6,
                    "ND2": True,
                    "H3": True,
                    "KR7": True,
                    "KR8": False,
                    "ND2_flow": 45.0,
                    "water_flow": 12.0,
                    "E1_level": 42.0,
                    "E1_ready": True,
                    "E1_voltage": True,
                    "PO1_level": 25.0,
                },
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
    assert features["pump_h1c"] == 1.0
    assert features["pump_nd1"] == 1.0
    assert features["oil_flow_after_pumps"] == 360.0
    assert features["oil_flow_to_elou"] == 300.0
    assert features["oil_elou_flow_gap"] == 60.0
    assert features["valve_kr1"] == 1.0
    assert features["valve_kr6"] == 1.0
    assert features["regulator_frc407"] == 80.0
    assert features["regulator_frc408"] == 6.0
    assert features["pump_nd2"] == 1.0
    assert features["pump_h3"] == 1.0
    assert features["valve_kr7"] == 1.0
    assert features["valve_kr8"] == 0.0
    assert features["nd1_flow"] == 12.0
    assert features["nd2_flow"] == 45.0
    assert features["water_flow"] == 12.0
    assert features["e1_level"] == 42.0
    assert features["e1_ready"] == 1.0
    assert features["e1_voltage"] == 1.0
    assert features["po1_level"] == 25.0
    assert features["combined_scenario"] == 0.0
    assert features["time_since_last_action_s"] == 2.0
    assert features["action_count_last_10s"] == 1.0
    assert features["scenario_step"] == 1.0
    assert features["previous_late_action_count"] == 2.0


def test_extracts_combined_cycle_feature_flag() -> None:
    request = RiskPredictionRequest(
        session_id=UUID("00000000-0000-0000-0000-000000000002"),
        scenario_code="oil-heating-elou-integrated-startup",
        window=[
            TelemetryPoint(
                simulation_time_ms=1_000,
                revision=1,
                sensors={"PRA1": 1.0, "TR2": 90.0},
            ),
        ],
    )

    features = extract_risk_features(request)

    assert features["combined_scenario"] == 1.0
