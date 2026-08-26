from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.explanation.service import narrative_service
from app.prediction.risk_model import risk_predictor
from app.schemas.contracts import (
    Debrief,
    DebriefRequest,
    ErrorExplanation,
    ErrorExplanationRequest,
    Recommendation,
    RecommendationRequest,
    RiskPrediction,
    RiskPredictionRequest,
)

router = APIRouter()
CONTRACT_MODEL_VERSION = "mock-ai-contract-v1"
MODELS_DIR = Path("/app/models")


@router.post("/v1/predict-risk", response_model=RiskPrediction)
async def predict_risk(request: RiskPredictionRequest) -> RiskPrediction:
    return risk_predictor.predict(request)


@router.get("/v1/models")
async def list_models() -> list[dict[str, Any]]:
    active_metadata = Path(
        os.getenv("AI_RISK_MODEL_METADATA_PATH", "/app/models/risk-catboost-v2.json")
    ).resolve()
    result: list[dict[str, Any]] = []

    if not MODELS_DIR.exists():
        return result

    for metadata_path in sorted(MODELS_DIR.glob("risk-catboost-*.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(metadata, dict):
            continue

        model_version = str(metadata.get("model_version") or metadata_path.stem)
        artifact_path = metadata_path.with_suffix(".cbm")
        feature_importances = metadata.get("feature_importances")
        if not isinstance(feature_importances, dict):
            feature_importances = {}

        top_features = sorted(
            (
                {"name": str(name), "importance": float(value)}
                for name, value in feature_importances.items()
                if isinstance(value, int | float)
            ),
            key=lambda item: item["importance"],
            reverse=True,
        )[:10]

        training_rows = int(metadata.get("training_rows") or 0)
        validation_rows = int(metadata.get("validation_rows") or 0)
        dataset_rows = int(metadata.get("dataset_rows") or training_rows + validation_rows)

        result.append(
            {
                **metadata,
                "model_version": model_version,
                "metadata_file": metadata_path.name,
                "artifact_file": artifact_path.name,
                "artifact_exists": artifact_path.exists(),
                "active": metadata_path.resolve() == active_metadata,
                "dataset_rows": dataset_rows,
                "top_features": top_features,
            }
        )

    return sorted(result, key=lambda item: str(item.get("model_version", "")), reverse=True)


@router.post("/v1/explain-error", response_model=ErrorExplanation)
async def explain_error(request: ErrorExplanationRequest) -> ErrorExplanation:
    return await narrative_service.explain_error(request)


@router.post("/v1/debrief", response_model=Debrief)
async def build_debrief(request: DebriefRequest) -> Debrief:
    return await narrative_service.build_debrief(request)


@router.post("/v1/recommend-training", response_model=Recommendation)
async def recommend_training(request: RecommendationRequest) -> Recommendation:
    if request.previous_errors:
        dominant = max(request.previous_errors, key=request.previous_errors.get)  # type: ignore[arg-type]
        rationale = f"Чаще всего встречается ошибка {dominant}."
    else:
        rationale = "Недостаточно истории ошибок для персональной рекомендации."
    return Recommendation(
        recommended_scenario_code=None,
        rationale=rationale,
        priority="medium",
        model=CONTRACT_MODEL_VERSION,
    )
