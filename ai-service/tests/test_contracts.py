from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_predict_risk_contract() -> None:
    response = client.post(
        "/v1/predict-risk",
        json={
            "session_id": "00000000-0000-0000-0000-000000000001",
            "scenario_code": "oil-heating-basic-startup",
            "operator_profile": {"previous_errors": {"LATE_ACTION": 3}},
            "window": [],
            "recent_actions": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk"] == 0.0
    assert payload["horizon_seconds"] == 10
    assert payload["model_version"] == "risk-model-unavailable-v1"


def test_explain_error_does_not_reclassify_error() -> None:
    response = client.post(
        "/v1/explain-error",
        json={
            "error_code": "WRONG_SEQUENCE",
            "severity": "warning",
            "expected_action": {"equipment_id": "H1A", "action": "start"},
            "actual_action": {"equipment_id": "H1B", "action": "start"},
            "process_context": {},
            "cause": [],
            "consequences": [],
            "regulation_context": [],
        },
    )

    assert response.status_code == 200
    assert "WRONG_SEQUENCE" in response.json()["summary"]
