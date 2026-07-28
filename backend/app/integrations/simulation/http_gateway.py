from collections.abc import AsyncIterator
from uuid import UUID

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from app.core.config import Settings
from app.integrations.simulation.dto import (
    CommandResult,
    ExternalSession,
    SimulationEvent,
    SimulationState,
)
from app.integrations.simulation.errors import (
    InvalidExternalPayloadError,
    SimulationProtocolError,
    SimulationSessionNotFoundError,
    SimulationTimeoutError,
    SimulationUnavailableError,
)
from app.integrations.simulation.mapping import (
    parse_external_command_result,
    parse_external_event_json,
    parse_external_session,
    parse_external_state,
)


class HttpSimulationGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self._settings.simulation_connect_timeout_seconds,
            read=self._settings.simulation_read_timeout_seconds,
            write=self._settings.simulation_read_timeout_seconds,
            pool=self._settings.simulation_connect_timeout_seconds,
        )

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._settings.simulation_api_key}",
        }
        if correlation_id is not None:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> object:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            base_url=self._settings.simulation_api_base_url,
            timeout=self._timeout(),
        )
        try:
            response = await client.request(method, path, json=json, headers=headers)
            if response.status_code == 404:
                raise SimulationSessionNotFoundError
            if response.status_code >= 500:
                raise SimulationUnavailableError
            if response.status_code >= 400:
                raise SimulationProtocolError
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()
        except httpx.TimeoutException as exc:
            raise SimulationTimeoutError from exc
        except httpx.TransportError as exc:
            raise SimulationUnavailableError from exc
        except ValueError as exc:
            raise InvalidExternalPayloadError from exc
        finally:
            if owns_client:
                await client.aclose()

    async def create_session(
        self,
        simulator_id: str,
        operator_id: UUID,
        local_session_id: UUID,
    ) -> ExternalSession:
        payload: dict[str, object] = {
            "simulator_id": simulator_id,
            "operator_id": str(operator_id),
            "metadata": {"local_session_id": str(local_session_id)},
        }
        response = await self._request(
            "POST",
            "/v1/sessions",
            json=payload,
            headers=self._headers(correlation_id=str(local_session_id)),
        )
        return parse_external_session(response)

    async def get_state(self, external_session_id: str) -> SimulationState:
        response = await self._request(
            "GET",
            f"/v1/sessions/{external_session_id}/state",
            headers=self._headers(),
        )
        return parse_external_state(response)

    async def send_command(
        self,
        external_session_id: str,
        command_id: UUID,
        equipment_id: str,
        action: str,
        payload: dict[str, object],
        expected_revision: int | None,
    ) -> CommandResult:
        command_payload: dict[str, object] = {
            "command_id": str(command_id),
            "equipment_id": equipment_id,
            "action": action,
            "payload": payload,
        }
        if expected_revision is not None:
            command_payload["expected_revision"] = expected_revision

        headers = self._headers(correlation_id=str(command_id))
        headers["Idempotency-Key"] = str(command_id)
        response = await self._request(
            "POST",
            f"/v1/sessions/{external_session_id}/commands",
            json=command_payload,
            headers=headers,
        )
        return parse_external_command_result(response)

    async def stop_session(self, external_session_id: str) -> None:
        await self._request(
            "POST",
            f"/v1/sessions/{external_session_id}/stop",
            headers=self._headers(),
        )

    async def stream_events(self, external_session_id: str) -> AsyncIterator[SimulationEvent]:
        url = f"{self._settings.simulation_ws_base_url}/v1/sessions/{external_session_id}/events"
        try:
            async with connect(
                url,
                additional_headers=self._headers(),
                open_timeout=self._settings.simulation_connect_timeout_seconds,
            ) as websocket:
                async for message in websocket:
                    yield parse_external_event_json(message)
        except TimeoutError as exc:
            raise SimulationTimeoutError from exc
        except (ConnectionClosed, InvalidHandshake, OSError) as exc:
            raise SimulationUnavailableError from exc
