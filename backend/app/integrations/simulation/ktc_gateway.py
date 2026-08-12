from collections.abc import AsyncIterator
from math import isfinite
from typing import cast
from uuid import UUID

import httpx

from app.core.config import Settings
from app.integrations.simulation.dto import (
    BoilerState,
    BoilerStatus,
    CommandResult,
    CommandStatus,
    EquipmentState,
    EquipmentStatus,
    ExternalSession,
    SimulationEvent,
    SimulationEventType,
    SimulationState,
)
from app.integrations.simulation.errors import (
    InvalidExternalPayloadError,
    SimulationProtocolError,
    SimulationTimeoutError,
    SimulationUnavailableError,
)
from app.repositories.simulators import KTC_OIL_HEATING_EXTERNAL_ID

KTC_EXTERNAL_SESSION_PREFIX = f"{KTC_OIL_HEATING_EXTERNAL_ID}:"
KTC_PUMPS = ("H1A", "H1B", "H1V")
KTC_REGULATORS = ("FRC404", "FRC405", "FRC406")
KTC_ACTIONS = {
    ("H1A", "start"): "start_pump_H1A",
    ("H1A", "stop"): "stop_pump_H1A",
    ("H1B", "start"): "start_pump_H1B",
    ("H1B", "stop"): "stop_pump_H1B",
    ("H1V", "start"): "start_pump_H1V",
    ("H1V", "stop"): "stop_pump_H1V",
    ("FRC404", "set"): "FRC404",
    ("FRC405", "set"): "FRC405",
    ("FRC406", "set"): "FRC406",
}
KGF_CM2_TO_BAR = 0.980665


class KtcOilHeatingGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._revision = 1

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self._settings.simulation_connect_timeout_seconds,
            read=self._settings.simulation_read_timeout_seconds,
            write=self._settings.simulation_read_timeout_seconds,
            pool=self._settings.simulation_connect_timeout_seconds,
        )

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> object:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            base_url=self._settings.ktc_api_base_url,
            timeout=self._timeout(),
        )
        try:
            response = await client.request(method, path, params=params)
            if response.status_code >= 500:
                raise SimulationUnavailableError
            if response.status_code >= 400:
                raise SimulationProtocolError
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
        del operator_id
        if simulator_id != KTC_OIL_HEATING_EXTERNAL_ID:
            raise SimulationProtocolError
        state = await self.get_state(f"{KTC_EXTERNAL_SESSION_PREFIX}{local_session_id}")
        return ExternalSession(
            session_id=f"{KTC_EXTERNAL_SESSION_PREFIX}{local_session_id}",
            status="active",
            state=state,
        )

    async def get_state(self, external_session_id: str) -> SimulationState:
        if not external_session_id.startswith(KTC_EXTERNAL_SESSION_PREFIX):
            raise SimulationProtocolError
        response = await self._request("GET", "/api/status/oilHeating")
        return self._map_status(response)

    async def send_command(
        self,
        external_session_id: str,
        command_id: UUID,
        equipment_id: str,
        action: str,
        payload: dict[str, object],
        expected_revision: int | None,
    ) -> CommandResult:
        del expected_revision
        if not external_session_id.startswith(KTC_EXTERNAL_SESSION_PREFIX):
            raise SimulationProtocolError
        ktc_action = KTC_ACTIONS.get((equipment_id, action))
        if ktc_action is None:
            return CommandResult(
                command_id=command_id,
                status=CommandStatus.REJECTED,
                code="COMMAND_REJECTED",
                message="Команда недоступна для блока подогрева нефти",
            )

        params = {"action": ktc_action}
        if equipment_id in KTC_REGULATORS:
            value = self._read_valve_percent(payload)
            if value is None:
                return CommandResult(
                    command_id=command_id,
                    status=CommandStatus.REJECTED,
                    code="INVALID_REGULATOR_VALUE",
                    message="Положение регулятора должно быть в диапазоне 0-100%",
                )
            params["value"] = str(value)

        await self._request(
            "POST",
            "/api/action/oilHeating",
            params=params,
        )
        self._revision += 1
        return CommandResult(command_id=command_id, status=CommandStatus.ACCEPTED)

    async def stop_session(self, external_session_id: str) -> None:
        if not external_session_id.startswith(KTC_EXTERNAL_SESSION_PREFIX):
            raise SimulationProtocolError
        for pump_id in KTC_PUMPS:
            await self._request(
                "POST",
                "/api/action/oilHeating",
                params={"action": KTC_ACTIONS[(pump_id, "stop")]},
            )
        self._revision += 1

    async def stream_events(self, external_session_id: str) -> AsyncIterator[SimulationEvent]:
        yield SimulationEvent(
            type=SimulationEventType.SESSION_READY,
            data={"status": "active"},
        )
        state = await self.get_state(external_session_id)
        yield SimulationEvent(
            type=SimulationEventType.STATE_SNAPSHOT,
            data=state.model_dump(mode="json"),
        )

    def _map_status(self, payload: object) -> SimulationState:
        if not isinstance(payload, dict):
            raise InvalidExternalPayloadError
        pumps = self._read_mapping(payload, "pumps")
        sensors = self._read_mapping(payload, "sensors")
        regulators = self._read_mapping(payload, "regulators")
        installation_output = self._read_optional_mapping(payload, "installation_output")

        pump_states = {
            pump_id: self._read_bool(pumps, pump_id)
            for pump_id in KTC_PUMPS
        }
        density = self._read_number(sensors, "QR5K3D")
        h1a_flow = self._read_number(sensors, "FQR117_1")
        h1v_flow = self._read_number(sensors, "FQR117_2")
        h1b_flow = 450.0 if pump_states["H1B"] else 0.0
        temperature_c = self._read_number(sensors, "TR41_1")
        pressure_bar = self._read_number(sensors, "PRA351") * KGF_CM2_TO_BAR

        return SimulationState(
            revision=self._revision,
            simulation_time_ms=self._revision * 1_000,
            boiler=BoilerState(
                temperature_c=temperature_c,
                pressure_bar=pressure_bar,
                status=BoilerStatus.RUNNING
                if any(pump_states.values())
                else BoilerStatus.IDLE,
            ),
            equipment={
                "H1A": EquipmentState(
                    status=self._equipment_status(pump_states["H1A"]),
                    flow_kg_h=h1a_flow * density,
                ),
                "H1B": EquipmentState(
                    status=self._equipment_status(pump_states["H1B"]),
                    flow_kg_h=h1b_flow * density,
                ),
                "H1V": EquipmentState(
                    status=self._equipment_status(pump_states["H1V"]),
                    flow_kg_h=h1v_flow * density,
                ),
            },
            alarms=[],
            process={
                "pumps": pumps,
                "sensors": sensors,
                "regulators": regulators,
                "installation_output": installation_output,
            },
        )

    @staticmethod
    def _equipment_status(is_running: bool) -> EquipmentStatus:
        return EquipmentStatus.RUNNING if is_running else EquipmentStatus.STOPPED

    @staticmethod
    def _read_mapping(payload: dict[str, object], field: str) -> dict[str, object]:
        value = payload.get(field)
        if not isinstance(value, dict):
            raise InvalidExternalPayloadError
        return cast(dict[str, object], value)

    @staticmethod
    def _read_optional_mapping(payload: dict[str, object], field: str) -> dict[str, object]:
        value = payload.get(field)
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise InvalidExternalPayloadError
        return cast(dict[str, object], value)

    @staticmethod
    def _read_bool(payload: dict[str, object], field: str) -> bool:
        value = payload.get(field)
        if not isinstance(value, bool):
            raise InvalidExternalPayloadError
        return value

    @staticmethod
    def _read_number(payload: dict[str, object], field: str) -> float:
        value = payload.get(field)
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise InvalidExternalPayloadError
        return float(value)

    @staticmethod
    def _read_valve_percent(payload: dict[str, object]) -> int | None:
        value = payload.get("value")
        if not isinstance(value, int | float) or isinstance(value, bool):
            return None
        if not isfinite(float(value)):
            return None
        normalized = round(float(value))
        if normalized < 0 or normalized > 100:
            return None
        return normalized
