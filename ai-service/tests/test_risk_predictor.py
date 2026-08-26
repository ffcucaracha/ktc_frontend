from pathlib import Path
from uuid import UUID
import json

from app.prediction.risk_model import MODEL_UNAVAILABLE_VERSION, RiskPredictor
from app.schemas.contracts import RiskPredictionRequest


def test_missing_model_returns_explicit_unavailable_prediction(tmp_path: Path) -> None:
    predictor = RiskPredictor(
        model_path=tmp_path / "missing.cbm",
        metadata_path=tmp_path / "missing.json",
    )
    request = RiskPredictionRequest(
        session_id=UUID("00000000-0000-0000-0000-000000000001"),
        scenario_code="oil-heating-basic-startup",
    )

    result = predictor.predict(request)

    assert result.risk == 0.0
    assert result.predicted_error_code is None
    assert result.model_version == MODEL_UNAVAILABLE_VERSION
    assert result.horizon_seconds == 10


def test_feature_contract_mismatch_disables_model(tmp_path: Path) -> None:
    model_path = tmp_path / "risk.cbm"
    metadata_path = tmp_path / "risk.json"
    model_path.write_text("not-a-real-catboost-model", encoding="utf-8")
    metadata_path.write_text(
        json.dumps({"feature_names": ["legacy_feature"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    predictor = RiskPredictor(model_path=model_path, metadata_path=metadata_path)
    request = RiskPredictionRequest(
        session_id=UUID("00000000-0000-0000-0000-000000000001"),
        scenario_code="oil-heating-basic-startup",
    )

    result = predictor.predict(request)

    assert result.risk == 0.0
    assert result.predicted_error_code is None
    assert result.model_version == MODEL_UNAVAILABLE_VERSION
