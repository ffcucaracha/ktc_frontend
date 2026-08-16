from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.features.risk import FEATURE_NAMES, extract_risk_features, feature_vector
from app.schemas.contracts import FeatureImportance, RiskPrediction, RiskPredictionRequest

DEFAULT_MODEL_PATH = Path(os.getenv("AI_RISK_MODEL_PATH", "/app/models/risk-catboost-v1.cbm"))
DEFAULT_METADATA_PATH = Path(
    os.getenv("AI_RISK_MODEL_METADATA_PATH", "/app/models/risk-catboost-v1.json")
)
HORIZON_SECONDS = 10
MODEL_UNAVAILABLE_VERSION = "risk-model-unavailable-v1"


@dataclass
class LoadedRiskModel:
    model: Any
    version: str
    threshold: float
    feature_importances: dict[str, float]


class RiskPredictor:
    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        metadata_path: Path = DEFAULT_METADATA_PATH,
    ) -> None:
        self._model_path = model_path
        self._metadata_path = metadata_path
        self._loaded: LoadedRiskModel | None = None
        self._load_attempted = False

    def predict(self, request: RiskPredictionRequest) -> RiskPrediction:
        features = extract_risk_features(request)
        loaded = self._load()
        if loaded is None:
            return RiskPrediction(
                risk=0.0,
                predicted_error_code=None,
                horizon_seconds=HORIZON_SECONDS,
                model_version=MODEL_UNAVAILABLE_VERSION,
                features=[],
            )

        probability = float(loaded.model.predict_proba([feature_vector(features)])[0][1])
        ranked = sorted(
            loaded.feature_importances.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:5]
        return RiskPrediction(
            risk=max(0.0, min(1.0, probability)),
            predicted_error_code=(
                "ERROR_IN_NEXT_10_SECONDS" if probability >= loaded.threshold else None
            ),
            horizon_seconds=HORIZON_SECONDS,
            model_version=loaded.version,
            features=[FeatureImportance(name=name, importance=value) for name, value in ranked],
        )

    def _load(self) -> LoadedRiskModel | None:
        if self._load_attempted:
            return self._loaded
        self._load_attempted = True
        if not self._model_path.exists() or not self._metadata_path.exists():
            return None

        from catboost import CatBoostClassifier

        metadata = json.loads(self._metadata_path.read_text(encoding="utf-8"))
        if metadata.get("feature_names") != FEATURE_NAMES:
            raise RuntimeError("Risk model feature contract does not match running AI service")

        model = CatBoostClassifier()
        model.load_model(str(self._model_path))
        self._loaded = LoadedRiskModel(
            model=model,
            version=str(metadata.get("model_version", "risk-catboost-unknown")),
            threshold=float(metadata.get("threshold", 0.5)),
            feature_importances={
                str(name): float(value)
                for name, value in metadata.get("feature_importances", {}).items()
            },
        )
        return self._loaded


risk_predictor = RiskPredictor()
