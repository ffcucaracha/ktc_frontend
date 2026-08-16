from fastapi import APIRouter

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
    return ErrorExplanation(
        summary=f"Зафиксирована ошибка {request.error_code}.",
        explanation=(
            "AI-service получил код ошибки и фактический контекст от application backend. "
            "Сервис не меняет классификацию и не придумывает новые факты."
        ),
        recommendation="Повторите соответствующий шаг учебного сценария.",
        sources=request.regulation_context,
        model=CONTRACT_MODEL_VERSION,
    )


@router.post("/v1/debrief", response_model=Debrief)
async def build_debrief(request: DebriefRequest) -> Debrief:
    score = request.session_result.get("score")
    weaknesses = list(dict.fromkeys(item.error_code for item in request.errors))
    return Debrief(
        short_summary=(
            f"Результат тренировки: {score}." if score is not None else "Тренировка завершена."
        ),
        strengths=[] if weaknesses else ["Классифицированные ошибки отсутствуют."],
        weaknesses=weaknesses,
        priority_actions=[f"Повторить работу с ошибкой {code}." for code in weaknesses[:3]],
        recommended_scenario_code=None,
        model=CONTRACT_MODEL_VERSION,
    )


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
