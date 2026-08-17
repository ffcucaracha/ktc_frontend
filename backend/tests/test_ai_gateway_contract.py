import asyncio
from uuid import uuid4

import httpx
import pytest

from app.integrations.ai.dto import RiskPredictionRequest
from app.integrations.ai.errors import AIIntegrationError, AIIntegrationErrorCode
from app.integrations.ai.http_gateway import HttpAIGateway
from app.integrations.ai.mock_gateway import MockAIGateway


@pytest.mark.asyncio
async def test_mock_ai_gateway_implements_risk_contract() -> None:
    gateway = MockAIGateway()
    response = await gateway.predict_risk(
        RiskPredictionRequest(session_id=uuid4(), scenario_code="oil-heating-basic-startup")
    )

    assert response.risk == 0.0
    assert response.predicted_error_code is None
    assert response.horizon_seconds == 10
    assert response.model_version == "mock-ai-contract-v1"


@pytest.mark.asyncio
async def test_http_ai_gateway_validates_response_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/predict-risk"
        return httpx.Response(
            200,
            json={
                "risk": 0.84,
                "predicted_error_code": "LATE_ACTION",
                "horizon_seconds": 10,
                "model_version": "risk-catboost-v1",
                "features": [{"name": "pressure_delta_10s", "importance": 0.31}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        gateway = HttpAIGateway(base_url="http://ai-service", client=client)
        response = await gateway.predict_risk(
            RiskPredictionRequest(session_id=uuid4(), scenario_code="oil-heating-basic-startup")
        )
    finally:
        await client.aclose()

    assert response.risk == 0.84
    assert response.predicted_error_code == "LATE_ACTION"
    assert response.features[0].name == "pressure_delta_10s"


@pytest.mark.asyncio
async def test_realtime_prediction_has_independent_short_timeout() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = HttpAIGateway(
        base_url="http://ai-service",
        prediction_timeout_seconds=0.01,
        client=client,
    )
    try:
        with pytest.raises(AIIntegrationError) as error:
            await gateway.predict_risk(
                RiskPredictionRequest(session_id=uuid4(), scenario_code="oil-heating-basic-startup")
            )
    finally:
        await client.aclose()

    assert error.value.code == AIIntegrationErrorCode.AI_TIMEOUT
