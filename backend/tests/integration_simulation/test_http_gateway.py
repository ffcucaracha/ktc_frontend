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
from app.integrations.simulation.factory import (
    create_default_simulation_gateway,
    create_simulation_gateway,
)
from app.integrations.simulation.http_gateway import HttpSimulationGateway
from app.integrations.simulation.ktc_gateway import (
    KTC_EXTERNAL_SESSION_PREFIX,
    KtcOilHeatingGateway,
)
from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.integrations.simulation.routing_gateway import RoutingSimulationGateway


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

    assert isinstance(create_default_simulation_gateway(mock_settings), MockSimulationGateway)
    assert isinstance(create_default_simulation_gateway(http_settings), HttpSimulationGateway)
    assert isinstance(create_simulation_gateway(mock_settings), RoutingSimulationGateway)


def test_factory_reuses_mock_gateway_for_process_local_fixture() -> None:
    mock_settings = settings().model_copy(update={"simulation_gateway_mode": "mock"})
    first = create_simulation_gateway(mock_settings)
    second = create_simulation_gateway(mock_settings)

    assert isinstance(first, RoutingSimulationGateway)
    assert isinstance(second, RoutingSimulationGateway)
    assert first._default_gateway is second._default_gateway


@pytest.mark.asyncio
async def test_ktc_gateway_maps_latest_oil_heating_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/status/oilHeating"
        return httpx.Response(
            200,
            json={
                "pumps": {"H1A": True, "H1B": False, "H1V": False},
                "sensors": {
                    "TR5K3T": 20,
                    "QR5K3D": 0.856,
                    "FQR117_1": 450.0,
                    "FQR117_2": 0.0,
                    "FYQR117": 450.0,
                    "TR41_1": 24,
                    "PRA351": 19.5,
                },
                "regulators": {
                    "FRC404": {"valve": 50},
                    "FRC405": {"valve": 0},
                    "FRC406": {"valve": 0},
                },
                "installation_output": {"oil_flow_exit": 225.0},
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://ktc.test",
    )
    gateway = KtcOilHeatingGateway(settings(), client=client)

    state = await gateway.get_state(f"{KTC_EXTERNAL_SESSION_PREFIX}local-session")

    assert state.equipment["H1A"].flow_kg_h == pytest.approx(385.2)
    assert state.process["installation_output"] == {"oil_flow_exit": 225.0}
    assert state.process["regulators"] == {
        "FRC404": {"valve": 50},
        "FRC405": {"valve": 0},
        "FRC406": {"valve": 0},
    }
    await client.aclose()


@pytest.mark.asyncio
async def test_ktc_gateway_sends_regulator_value() -> None:
    command_id = UUID("735f13c8-6700-4ad6-b86b-f5d2e8b683d3")
    captured_params: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://ktc.test",
    )
    gateway = KtcOilHeatingGateway(settings(), client=client)

    result = await gateway.send_command(
        external_session_id=f"{KTC_EXTERNAL_SESSION_PREFIX}local-session",
        command_id=command_id,
        equipment_id="FRC404",
        action="set",
        payload={"value": 67},
        expected_revision=1,
    )

    assert result.status == CommandStatus.ACCEPTED
    assert captured_params == {"action": "FRC404", "value": "67"}
    await client.aclose()


@pytest.mark.asyncio
async def test_ktc_gateway_rejects_invalid_regulator_value() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
        base_url="http://ktc.test",
    )
    gateway = KtcOilHeatingGateway(settings(), client=client)

    result = await gateway.send_command(
        external_session_id=f"{KTC_EXTERNAL_SESSION_PREFIX}local-session",
        command_id=UUID("735f13c8-6700-4ad6-b86b-f5d2e8b683d3"),
        equipment_id="FRC404",
        action="set",
        payload={"value": 101},
        expected_revision=1,
    )

    assert result.status == CommandStatus.REJECTED
    assert result.code == "INVALID_REGULATOR_VALUE"
    await client.aclose()
