from app.integrations.ai.dto import (
    Debrief,
    DebriefRequest,
    ErrorExplanation,
    ErrorExplanationRequest,
    Recommendation,
    RecommendationRequest,
    RiskPrediction,
    RiskPredictionRequest,
)


class MockAIGateway:
    """Deterministic contract stub used until a real AI service/model is enabled."""

    async def predict_risk(self, request: RiskPredictionRequest) -> RiskPrediction:
        del request
        return RiskPrediction(
            risk=0.0,
            predicted_error_code=None,
            horizon_seconds=10,
            model_version="mock-ai-contract-v1",
            features=[],
        )

    async def explain_error(self, request: ErrorExplanationRequest) -> ErrorExplanation:
        return ErrorExplanation(
            summary=f"Зафиксирована ошибка {request.error_code}.",
            explanation=(
                "Объяснение построено только по структурированным фактам, переданным "
                "application backend; код ошибки не определяется AI-сервисом."
            ),
            recommendation="Повторите соответствующий шаг учебного сценария.",
            sources=request.regulation_context,
            model="mock-ai-contract-v1",
        )

    async def build_debrief(self, request: DebriefRequest) -> Debrief:
        score = request.session_result.get("score")
        errors = [item.error_code for item in request.errors]
        weaknesses = list(dict.fromkeys(errors))
        return Debrief(
            short_summary=(
                f"Результат тренировки: {score}." if score is not None else "Тренировка завершена."
            ),
            strengths=[] if errors else ["Сценарий выполнен без классифицированных ошибок."],
            weaknesses=weaknesses,
            priority_actions=[f"Повторить работу с ошибкой {code}." for code in weaknesses[:3]],
            recommended_scenario_code=None,
            model="mock-ai-contract-v1",
        )

    async def recommend_training(self, request: RecommendationRequest) -> Recommendation:
        if request.previous_errors:
            dominant = max(request.previous_errors, key=request.previous_errors.get)  # type: ignore[arg-type]
            rationale = f"Чаще всего встречается ошибка {dominant}."
        else:
            rationale = "Недостаточно истории ошибок для персональной рекомендации."
        return Recommendation(
            recommended_scenario_code=None,
            rationale=rationale,
            priority="medium",
            model="mock-ai-contract-v1",
        )
