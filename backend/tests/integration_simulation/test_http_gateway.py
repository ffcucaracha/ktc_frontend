from uuid import UUID

import httpx
import pytest

from app.core.config import Settings
from app.integrations.simulation.dto import CommandStatus
from app.integrations.simulation.errors import (
    InvalidExternalPayloadError,
    SimulationSessionNotFoundError,
    SimulationTimeoutError,
    SimulationUnavailableError,
)
from app.integrations.simulation.factory import create_simulation_gateway
from app.integrations.simulation.http_gateway import HttpSimulationGateway
from app.integrations.simulation.mock_gateway import MockSimulationGateway


def settings() -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://trainer:trainer@localhost:5432/trainer",
        CORS_ORIGINS="http://localhost:5173",
        JWT_SECRET="change-me-in-local-development-only-32-bytes",
        SIMULATION_API_KEY="test-api-key",
        SIMULATION_API_BASE_URL="http://simulation.test",
        SIMULATION_WS_BASE_URL="ws://simulation.test",
    )


@pytest.mark.asyncio
async def test_http_gateway_sends_command_idempotency_key_and_maps_response() -> None:
    command_id = UUID("735f13c8-6700-4ad6-b86b-f5d2e8b683d3")
    captured_headers: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_headers["authorization"] = request.headers["Authorization"]
        captured_headers["idempotency_key"] = request.headers["Idempotency-Key"]
        return httpx.Response(200, json={"command_id": str(command_id), "status": "accepted"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://simulation.test",
    )
    gateway = HttpSimulationGateway(settings(), client=client)

    result = await gateway.send_command(
        external_session_id="external-session",
        command_id=command_id,
        equipment_id="steam_supply_pump",
        action="start",
        payload={},
        expected_revision=1,
    )

    assert result.status == CommandStatus.ACCEPTED
    assert captured_headers["authorization"] == "Bearer test-api-key"
    assert captured_headers["idempotency_key"] == str(command_id)
    await client.aclose()


@pytest.mark.asyncio
async def test_http_gateway_maps_errors_and_invalid_payload() -> None:
    async def not_found(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "missing"})

    async def unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    async def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"bad": "payload"})

    async def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    with pytest.raises(SimulationSessionNotFoundError):
        await HttpSimulationGateway(
            settings(),
            client=httpx.AsyncClient(
                transport=httpx.MockTransport(not_found),
                base_url="http://simulation.test",
            ),
        ).get_state("missing")

    with pytest.raises(SimulationUnavailableError):
        await HttpSimulationGateway(
            settings(),
            client=httpx.AsyncClient(
                transport=httpx.MockTransport(unavailable),
                base_url="http://simulation.test",
            ),
        ).get_state("unavailable")

    with pytest.raises(InvalidExternalPayloadError):
        await HttpSimulationGateway(
            settings(),
            client=httpx.AsyncClient(
                transport=httpx.MockTransport(malformed),
                base_url="http://simulation.test",
            ),
        ).get_state("malformed")

    with pytest.raises(SimulationTimeoutError):
        await HttpSimulationGateway(
            settings(),
            client=httpx.AsyncClient(
                transport=httpx.MockTransport(timeout),
                base_url="http://simulation.test",
            ),
        ).get_state("timeout")


def test_factory_selects_gateway_by_mode() -> None:
    mock_settings = settings().model_copy(update={"simulation_gateway_mode": "mock"})
    http_settings = settings().model_copy(update={"simulation_gateway_mode": "http"})

    assert isinstance(create_simulation_gateway(mock_settings), MockSimulationGateway)
    assert isinstance(create_simulation_gateway(http_settings), HttpSimulationGateway)


def test_factory_reuses_mock_gateway_for_process_local_fixture() -> None:
    mock_settings = settings().model_copy(update={"simulation_gateway_mode": "mock"})

    assert create_simulation_gateway(mock_settings) is create_simulation_gateway(mock_settings)
