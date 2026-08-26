from scripts.generate_dataset import build_rows


def test_dataset_labels_future_error_without_using_future_action() -> None:
    session = {
        "session_id": "00000000-0000-0000-0000-000000000001",
        "scenario_code": "oil-heating-basic-startup",
        "snapshots": [
            {
                "simulation_time_ms": 10_000,
                "revision": 1,
                "sensors": {"PRA1": 1.0, "TR2": 90.0, "FQR117_1": 100.0},
                "pumps": {},
                "valves": {},
                "regulators": {},
                "dosing": {},
                "elou": {},
                "alarms": [],
            },
            {
                "simulation_time_ms": 20_000,
                "revision": 2,
                "sensors": {"PRA1": 1.2, "TR2": 92.0, "FQR117_1": 120.0},
                "pumps": {"H1A": True, "H1C": True},
                "valves": {"KR1": True, "KR6": True},
                "regulators": {"FRC404": 50},
                "dosing": {"ND1_flow": 10.0, "ND1_target": 10.0},
                "elou": {
                    "FQR118": 110.0,
                    "FRC407_valve": 80,
                    "ND2": True,
                    "ND2_flow": 45.0,
                    "E1_level": 35.0,
                    "E1_ready": True,
                },
                "alarms": [],
            },
        ],
        "actions": [
            {"simulation_time_ms": 25_000, "equipment_id": "H1B", "action": "start", "payload": {}}
        ],
        "errors": [{"occurred_at_ms": 25_000, "error_type": "LATE_ACTION"}],
    }

    rows = build_rows(session)

    assert rows[0]["target_error_next_10s"] == 0
    assert rows[1]["target_error_next_10s"] == 1
    assert rows[1]["future_error_code"] == "LATE_ACTION"
    assert rows[1]["scenario_step"] == 0.0
    assert rows[1]["pump_h1c"] == 1.0
    assert rows[1]["valve_kr6"] == 1.0
    assert rows[1]["regulator_frc407"] == 80.0
    assert rows[1]["pump_nd2"] == 1.0
    assert rows[1]["e1_level"] == 35.0
