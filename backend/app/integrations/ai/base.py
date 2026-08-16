from typing import Protocol

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


class AIGateway(Protocol):
    async def predict_risk(self, request: RiskPredictionRequest) -> RiskPrediction: ...

    async def explain_error(self, request: ErrorExplanationRequest) -> ErrorExplanation: ...

    async def build_debrief(self, request: DebriefRequest) -> Debrief: ...

    async def recommend_training(self, request: RecommendationRequest) -> Recommendation: ...
