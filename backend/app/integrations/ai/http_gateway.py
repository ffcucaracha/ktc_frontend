from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

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
from app.integrations.ai.errors import AIIntegrationError, AIIntegrationErrorCode

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class HttpAIGateway:
    def __init__(
        self,
        *,
        base_url: str,
        connect_timeout_seconds: float = 3.0,
        read_timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=read_timeout_seconds,
            pool=connect_timeout_seconds,
        )
        self._client = client

    async def predict_risk(self, request: RiskPredictionRequest) -> RiskPrediction:
        return await self._post("/v1/predict-risk", request, RiskPrediction)

    async def explain_error(self, request: ErrorExplanationRequest) -> ErrorExplanation:
        return await self._post("/v1/explain-error", request, ErrorExplanation)

    async def build_debrief(self, request: DebriefRequest) -> Debrief:
        return await self._post("/v1/debrief", request, Debrief)

    async def recommend_training(self, request: RecommendationRequest) -> Recommendation:
        return await self._post("/v1/recommend-training", request, Recommendation)

    async def _post(
        self,
        path: str,
        request: BaseModel,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                f"{self._base_url}{path}",
                json=request.model_dump(mode="json"),
            )
            response.raise_for_status()
            return response_model.model_validate(response.json())
        except httpx.TimeoutException as exc:
            raise AIIntegrationError(
                AIIntegrationErrorCode.AI_TIMEOUT,
                "AI service request timed out",
            ) from exc
        except httpx.HTTPError as exc:
            raise AIIntegrationError(
                AIIntegrationErrorCode.AI_SERVICE_UNAVAILABLE,
                "AI service is unavailable",
            ) from exc
        except (ValueError, ValidationError) as exc:
            raise AIIntegrationError(
                AIIntegrationErrorCode.AI_PROTOCOL_ERROR,
                "AI service returned an invalid payload",
            ) from exc
        finally:
            if owns_client:
                await client.aclose()
