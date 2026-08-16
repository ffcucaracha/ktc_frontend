from scripts.generate_dataset import build_rows


def test_dataset_labels_future_error_without_using_future_action() -> None:
    session = {
        "session_id": "00000000-0000-0000-0000-000000000001",
        "scenario_code": "oil-heating-basic-startup",
        "snapshots": [
            {
                "simulation_time_ms": 10_000,
                "revision": 1,
                "sensors": {"PRA351": 1.0, "TR41_1": 90.0},
                "pumps": {},
                "regulators": {},
                "alarms": [],
            },
            {
                "simulation_time_ms": 20_000,
                "revision": 2,
                "sensors": {"PRA351": 1.2, "TR41_1": 92.0},
                "pumps": {},
                "regulators": {},
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
