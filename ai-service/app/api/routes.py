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


@router.post("/v1/predict-risk", response_model=RiskPrediction)
async def predict_risk(request: RiskPredictionRequest) -> RiskPrediction:
    return risk_predictor.predict(request)


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
