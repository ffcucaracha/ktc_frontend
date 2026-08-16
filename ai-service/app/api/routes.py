from fastapi import APIRouter

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
MODEL_VERSION = "mock-ai-contract-v1"


@router.post("/v1/predict-risk", response_model=RiskPrediction)
async def predict_risk(request: RiskPredictionRequest) -> RiskPrediction:
    del request
    return RiskPrediction(
        risk=0.0,
        predicted_error_code=None,
        horizon_seconds=10,
        model_version=MODEL_VERSION,
        features=[],
    )


@router.post("/v1/explain-error", response_model=ErrorExplanation)
async def explain_error(request: ErrorExplanationRequest) -> ErrorExplanation:
    return ErrorExplanation(
        summary=f"Зафиксирована ошибка {request.error_code}.",
        explanation=(
            "AI-service получил код ошибки и фактический контекст от application backend. "
            "На этом этапе сервис не меняет классификацию и не придумывает новые факты."
        ),
        recommendation="Повторите соответствующий шаг учебного сценария.",
        sources=request.regulation_context,
        model=MODEL_VERSION,
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
        model=MODEL_VERSION,
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
        model=MODEL_VERSION,
    )
