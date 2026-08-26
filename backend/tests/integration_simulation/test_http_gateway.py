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
    KTC_COMBINED_EXTERNAL_SESSION_PREFIX,
    KTC_EXTERNAL_SESSION_PREFIX,
    KtcOilHeatingElouGateway,
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


def oil_heating_status_payload() -> dict[str, object]:
    return {
        "valves": {
            "KR1": True,
            "KR2": False,
            "KR3": False,
            "KR4": False,
            "KR5": False,
            "KR6": True,
        },
        "pumps": {"H1A": True, "H1B": False, "H1C": False, "ND1": True},
        "sensors_in": {
            "TR1": 20,
            "QR1": 0.856,
        },
        "flow_meters": {
            "FQR117_1": 450.0,
            "FQR117_2": 0.0,
            "FQR117_3": 0.0,
        },
        "collector": {
            "TR1_collector": 20,
            "PRA1": 19.5,
        },
        "regulators": {
            "FRC404": 50,
            "FRC405": 0,
            "FRC406": 0,
        },
        "output": {
            "KR6": True,
            "TR2": 124.0,
            "oil_flow_exit": 225.0,
        },
        "dosing": {
            "ND1_flow": 10.0,
            "ND1_target": 10.0,
            "ND1_error": False,
        },
        "errors": {
            "process_stopped": False,
            "stop_reason": "",
            "KR6_error": False,
            "overheat_error": False,
            "pump_broken": {"H1A": False, "H1B": False, "H1C": False},
        },
    }


def elou_status_payload() -> dict[str, object]:
    return {
        "FQR118": 180.0,
        "FRC407_valve": 80,
        "ND2": True,
        "ND2_flow": 45.0,
        "ND2_error": False,
        "IS101_active": False,
        "H3": True,
        "FRC408_valve": 6,
        "water_flow": 12.0,
        "E1_level": 42.0,
        "E1_voltage": True,
        "E1_ready": True,
        "E1_error": False,
        "PO1_level": 25.0,
        "KR7": True,
        "KR7_error": False,
        "KR8": False,
        "FQR119_1": 180.0,
        "H3_error": False,
        "PO1_error": False,
        "process_stopped": False,
        "stop_reason": "",
    }


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
        return httpx.Response(200, json=oil_heating_status_payload())

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://ktc.test",
    )
    gateway = KtcOilHeatingGateway(settings(), client=client)

    state = await gateway.get_state(f"{KTC_EXTERNAL_SESSION_PREFIX}local-session")

    assert state.equipment["H1A"].flow_kg_h == pytest.approx(385.2)
    assert state.equipment["ND1"].status == "running"
    assert state.process["output"] == {"KR6": True, "TR2": 124.0, "oil_flow_exit": 225.0}
    assert state.process["regulators"] == {"FRC404": 50, "FRC405": 0, "FRC406": 0}
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
    assert captured_params == {"action": "set_FRC404", "value": "67"}
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


@pytest.mark.asyncio
async def test_ktc_combined_gateway_maps_oil_heating_and_elou_payloads() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/status/oilHeating":
            return httpx.Response(200, json=oil_heating_status_payload())
        if request.url.path == "/api/status/elou":
            return httpx.Response(200, json=elou_status_payload())
        return httpx.Response(404)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://ktc.test",
    )
    gateway = KtcOilHeatingElouGateway(settings(), client=client)

    state = await gateway.get_state(f"{KTC_COMBINED_EXTERNAL_SESSION_PREFIX}local-session")

    assert state.process["elou"]["FQR118"] == 180.0
    assert state.process["combined"] == {
        "oil_output_flow": 225.0,
        "elou_input_flow": 180.0,
        "elou_output_flow": 180.0,
    }
    assert state.equipment["ND2"].status == "running"
    assert state.equipment["H3"].flow_kg_h == pytest.approx(12.0)
    assert state.equipment["E1"].status == "running"
    await client.aclose()


@pytest.mark.asyncio
async def test_ktc_combined_gateway_sends_elou_command() -> None:
    command_id = UUID("735f13c8-6700-4ad6-b86b-f5d2e8b683d3")
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://ktc.test",
    )
    gateway = KtcOilHeatingElouGateway(settings(), client=client)

    result = await gateway.send_command(
        external_session_id=f"{KTC_COMBINED_EXTERNAL_SESSION_PREFIX}local-session",
        command_id=command_id,
        equipment_id="FRC407",
        action="set",
        payload={"value": 80},
        expected_revision=1,
    )

    assert result.status == CommandStatus.ACCEPTED
    assert captured == {"path": "/api/action/elou", "action": "set_FRC407", "value": "80"}
    await client.aclose()
