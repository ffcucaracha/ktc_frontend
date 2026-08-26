from collections.abc import AsyncIterator
from copy import deepcopy
from math import isfinite
from typing import cast
from uuid import UUID

import httpx

from app.core.config import Settings
from app.integrations.simulation.dto import (
    Alarm,
    AlarmSeverity,
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
from app.repositories.simulators import (
    KTC_OIL_HEATING_ELOU_EXTERNAL_ID,
    KTC_OIL_HEATING_EXTERNAL_ID,
)

KTC_EXTERNAL_SESSION_PREFIX = f"{KTC_OIL_HEATING_EXTERNAL_ID}:"
KTC_COMBINED_EXTERNAL_SESSION_PREFIX = f"{KTC_OIL_HEATING_ELOU_EXTERNAL_ID}:"
KTC_PUMPS = ("H1A", "H1B", "H1C")
KTC_VALVES = ("KR1", "KR2", "KR3", "KR4", "KR5", "KR6")
KTC_REGULATORS = ("FRC404", "FRC405", "FRC406")
KTC_ELOU_REGULATORS = ("FRC407", "FRC408")
KTC_ELOU_PUMPS = ("ND2", "H3")
KTC_ELOU_VALVES = ("KR7", "KR8")
KTC_ACTIONS = {
    ("H1A", "start"): "start_H1A",
    ("H1A", "stop"): "stop_H1A",
    ("H1B", "start"): "start_H1B",
    ("H1B", "stop"): "stop_H1B",
    ("H1C", "start"): "start_H1C",
    ("H1C", "stop"): "stop_H1C",
    ("ND1", "start"): "start_ND1",
    ("ND1", "stop"): "stop_ND1",
    ("ND1", "set"): "set_ND1_flow",
    ("QR1", "set"): "set_QR1",
    ("plant", "reset"): "reset_plant",
    ("FRC404", "set"): "set_FRC404",
    ("FRC405", "set"): "set_FRC405",
    ("FRC406", "set"): "set_FRC406",
    **{(valve_id, "open"): f"open_{valve_id}" for valve_id in KTC_VALVES},
    **{(valve_id, "close"): f"close_{valve_id}" for valve_id in KTC_VALVES},
}
KTC_ELOU_ACTIONS = {
    ("FRC407", "set"): "set_FRC407",
    ("FRC408", "set"): "set_FRC408",
    ("ND2", "start"): "start_ND2",
    ("ND2", "stop"): "stop_ND2",
    ("ND2", "set"): "set_ND2_flow",
    ("H3", "start"): "start_H3",
    ("H3", "stop"): "stop_H3",
    ("KR7", "open"): "open_KR7",
    ("KR7", "close"): "close_KR7",
    ("KR8", "open"): "open_KR8",
    ("KR8", "close"): "close_KR8",
    ("E1", "apply_voltage"): "apply_E1_voltage",
}
KGF_CM2_TO_BAR = 0.980665


class KtcOilHeatingGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._revision = 1
        self._last_status_payload: dict[str, object] | None = None

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
        elif (equipment_id, action) == ("ND1", "set"):
            value = self._read_valve_percent(payload)
            if value is None:
                return CommandResult(
                    command_id=command_id,
                    status=CommandStatus.REJECTED,
                    code="INVALID_SETPOINT_VALUE",
                    message="Уставка должна быть числом в диапазоне 0-100",
                )
            params["value"] = str(value)
        elif (equipment_id, action) == ("QR1", "set"):
            density_value = self._read_float_setpoint(payload, minimum=0.8, maximum=0.92)
            if density_value is None:
                return CommandResult(
                    command_id=command_id,
                    status=CommandStatus.REJECTED,
                    code="INVALID_DENSITY_VALUE",
                    message="Плотность должна быть в диапазоне 0.800-0.920 g/cm3",
                )
            params["value"] = f"{density_value:.3f}"

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
        await self._request(
            "POST",
            "/api/action/oilHeating",
            params={"action": KTC_ACTIONS[("ND1", "stop")]},
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
        typed_payload = cast(dict[str, object], payload)
        pumps = self._read_mapping(typed_payload, "pumps")
        valves = self._read_optional_mapping(typed_payload, "valves")
        sensors_in = self._read_mapping(typed_payload, "sensors_in")
        flow_meters = self._read_mapping(typed_payload, "flow_meters")
        collector = self._read_mapping(typed_payload, "collector")
        regulators = self._read_mapping(typed_payload, "regulators")
        output = self._read_mapping(typed_payload, "output")
        dosing = self._read_optional_mapping(typed_payload, "dosing")
        errors = self._read_optional_mapping(typed_payload, "errors")

        pump_states = {pump_id: self._read_bool(pumps, pump_id) for pump_id in KTC_PUMPS}
        nd1_running = self._read_optional_bool(pumps, "ND1")
        density = self._read_number(sensors_in, "QR1")
        h1a_flow = self._read_number(flow_meters, "FQR117_1")
        h1b_flow = self._read_number(flow_meters, "FQR117_2")
        h1c_flow = self._read_number(flow_meters, "FQR117_3")
        temperature_c = self._read_number(output, "TR2")
        pressure_bar = self._read_number(collector, "PRA1") * KGF_CM2_TO_BAR

        external_revision = self._read_optional_nonnegative_int(typed_payload, "revision")
        external_simulation_time_ms = self._read_optional_nonnegative_int(
            typed_payload,
            "simulation_time_ms",
        )
        revision = self._resolve_revision(typed_payload, external_revision)
        simulation_time_ms = (
            external_simulation_time_ms
            if external_simulation_time_ms is not None
            else revision * 1_000
        )

        process_payload = {
            "valves": valves,
            "pumps": pumps,
            "sensors_in": sensors_in,
            "flow_meters": flow_meters,
            "collector": collector,
            "regulators": regulators,
            "output": output,
            "dosing": dosing,
            "errors": errors,
            "timeline_metadata": {
                "revision_source": (
                    "ktc_backend" if external_revision is not None else "gateway_fallback"
                ),
                "simulation_time_source": (
                    "ktc_backend"
                    if external_simulation_time_ms is not None
                    else "gateway_fallback"
                ),
                "external_revision": external_revision,
                "external_simulation_time_ms": external_simulation_time_ms,
            },
            "raw": deepcopy(typed_payload),
        }

        self._last_status_payload = deepcopy(typed_payload)

        return SimulationState(
            revision=revision,
            simulation_time_ms=simulation_time_ms,
            boiler=BoilerState(
                temperature_c=temperature_c,
                pressure_bar=pressure_bar,
                status=BoilerStatus.RUNNING if any(pump_states.values()) else BoilerStatus.IDLE,
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
                "H1C": EquipmentState(
                    status=self._equipment_status(pump_states["H1C"]),
                    flow_kg_h=h1c_flow * density,
                ),
                "ND1": EquipmentState(
                    status=self._equipment_status(nd1_running),
                    flow_kg_h=self._read_optional_number(dosing, "ND1_flow"),
                ),
            },
            alarms=self._map_alarms(dosing, errors),
            process=process_payload,
        )

    def _resolve_revision(
        self,
        payload: dict[str, object],
        external_revision: int | None,
    ) -> int:
        if external_revision is not None:
            self._revision = external_revision
            return external_revision

        if self._last_status_payload is not None and payload != self._last_status_payload:
            self._revision += 1
        return self._revision

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
    def _read_optional_bool(payload: dict[str, object], field: str) -> bool:
        value = payload.get(field)
        if value is None:
            return False
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
    def _read_optional_number(payload: dict[str, object], field: str) -> float:
        value = payload.get(field)
        if value is None:
            return 0.0
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise InvalidExternalPayloadError
        return float(value)

    @staticmethod
    def _read_optional_nonnegative_int(payload: dict[str, object], field: str) -> int | None:
        value = payload.get(field)
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise InvalidExternalPayloadError
        return value

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

    @staticmethod
    def _read_float_setpoint(
        payload: dict[str, object],
        *,
        minimum: float,
        maximum: float,
    ) -> float | None:
        value = payload.get("value")
        if not isinstance(value, int | float) or isinstance(value, bool):
            return None
        normalized = float(value)
        if not isfinite(normalized) or normalized < minimum or normalized > maximum:
            return None
        return normalized

    @classmethod
    def _map_alarms(
        cls,
        dosing: dict[str, object],
        errors: dict[str, object],
    ) -> list[Alarm]:
        alarms: list[Alarm] = []
        if cls._read_optional_bool(errors, "process_stopped"):
            reason = errors.get("stop_reason")
            alarms.append(
                Alarm(
                    code="KTC_PROCESS_STOPPED",
                    severity=AlarmSeverity.CRITICAL,
                    message=str(reason) if reason else "Процесс остановлен",
                    active=True,
                )
            )
        if cls._read_optional_bool(errors, "KR6_error"):
            alarms.append(
                Alarm(
                    code="KTC_KR6_TEMPERATURE",
                    severity=AlarmSeverity.WARNING,
                    message="KR6 нельзя открыть вне диапазона 120-140 C",
                    active=True,
                )
            )
        if cls._read_optional_bool(errors, "overheat_error"):
            alarms.append(
                Alarm(
                    code="KTC_TEMPERATURE_LIMIT",
                    severity=AlarmSeverity.CRITICAL,
                    message="Температура вышла за допустимые пределы при открытом KR6",
                    active=True,
                )
            )
        if cls._read_optional_bool(dosing, "ND1_error"):
            alarms.append(
                Alarm(
                    code="KTC_ND1_DOSING",
                    severity=AlarmSeverity.WARNING,
                    message="Ошибка дозирования деэмульгатора ND1",
                    active=True,
                )
            )

        pump_broken = errors.get("pump_broken")
        if isinstance(pump_broken, dict):
            for pump_id in KTC_PUMPS:
                if cls._read_optional_bool(cast(dict[str, object], pump_broken), pump_id):
                    alarms.append(
                        Alarm(
                            code=f"KTC_PUMP_BROKEN_{pump_id}",
                            severity=AlarmSeverity.CRITICAL,
                            message=f"Поломка насоса {pump_id}",
                            active=True,
                        )
                    )
        return alarms


class KtcOilHeatingElouGateway(KtcOilHeatingGateway):
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(settings, client)
        self._combined_revision = 1
        self._combined_last_status_payload: dict[str, object] | None = None

    async def create_session(
        self,
        simulator_id: str,
        operator_id: UUID,
        local_session_id: UUID,
    ) -> ExternalSession:
        del operator_id
        if simulator_id != KTC_OIL_HEATING_ELOU_EXTERNAL_ID:
            raise SimulationProtocolError
        state = await self.get_state(f"{KTC_COMBINED_EXTERNAL_SESSION_PREFIX}{local_session_id}")
        return ExternalSession(
            session_id=f"{KTC_COMBINED_EXTERNAL_SESSION_PREFIX}{local_session_id}",
            status="active",
            state=state,
        )

    async def get_state(self, external_session_id: str) -> SimulationState:
        if not external_session_id.startswith(KTC_COMBINED_EXTERNAL_SESSION_PREFIX):
            raise SimulationProtocolError
        oil_response = await self._request("GET", "/api/status/oilHeating")
        elou_response = await self._request("GET", "/api/status/elou")
        return self._map_combined_status(oil_response, elou_response)

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
        if not external_session_id.startswith(KTC_COMBINED_EXTERNAL_SESSION_PREFIX):
            raise SimulationProtocolError

        if (equipment_id, action) == ("plant", "reset"):
            await self._request(
                "POST",
                "/api/action/oilHeating",
                params={"action": KTC_ACTIONS[("plant", "reset")]},
            )
            await self._request(
                "POST",
                "/api/action/elou",
                params={"action": "reset_plant"},
            )
            self._combined_revision += 1
            return CommandResult(command_id=command_id, status=CommandStatus.ACCEPTED)

        oil_action = KTC_ACTIONS.get((equipment_id, action))
        if oil_action is not None:
            result = await super().send_command(
                external_session_id=f"{KTC_EXTERNAL_SESSION_PREFIX}combined",
                command_id=command_id,
                equipment_id=equipment_id,
                action=action,
                payload=payload,
                expected_revision=None,
            )
            if result.status == CommandStatus.ACCEPTED:
                self._combined_revision += 1
            return result

        elou_action = KTC_ELOU_ACTIONS.get((equipment_id, action))
        if elou_action is None:
            return CommandResult(
                command_id=command_id,
                status=CommandStatus.REJECTED,
                code="COMMAND_REJECTED",
                message="Команда недоступна для комбинированного тренажера",
            )

        params = {"action": elou_action}
        if equipment_id in KTC_ELOU_REGULATORS or (equipment_id, action) == ("ND2", "set"):
            value = self._read_valve_percent(payload)
            if value is None:
                return CommandResult(
                    command_id=command_id,
                    status=CommandStatus.REJECTED,
                    code="INVALID_SETPOINT_VALUE",
                    message="Уставка должна быть числом в диапазоне 0-100",
                )
            params["value"] = str(value)

        await self._request("POST", "/api/action/elou", params=params)
        self._combined_revision += 1
        return CommandResult(command_id=command_id, status=CommandStatus.ACCEPTED)

    async def stop_session(self, external_session_id: str) -> None:
        if not external_session_id.startswith(KTC_COMBINED_EXTERNAL_SESSION_PREFIX):
            raise SimulationProtocolError
        for endpoint, actions in (
            ("/api/action/oilHeating", ("stop_H1A", "stop_H1B", "stop_H1C", "stop_ND1")),
            ("/api/action/elou", ("stop_ND2", "stop_H3", "close_KR7", "close_KR8")),
        ):
            for action in actions:
                await self._request("POST", endpoint, params={"action": action})
        self._combined_revision += 1

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

    def _map_combined_status(self, oil_payload: object, elou_payload: object) -> SimulationState:
        if not isinstance(elou_payload, dict):
            raise InvalidExternalPayloadError
        oil_state = self._map_status(oil_payload)
        elou = cast(dict[str, object], elou_payload)
        combined_payload = {
            "oilHeating": deepcopy(oil_payload),
            "elou": deepcopy(elou),
        }
        revision = self._resolve_combined_revision(combined_payload)
        process = {
            **oil_state.process,
            "elou": deepcopy(elou),
            "combined": {
                "oil_output_flow": self._read_number(
                    self._read_mapping(cast(dict[str, object], oil_payload), "output"),
                    "oil_flow_exit",
                ),
                "elou_input_flow": self._read_number(elou, "FQR118"),
                "elou_output_flow": self._read_number(elou, "FQR119_1"),
            },
        }
        equipment = {
            **oil_state.equipment,
            "ND2": EquipmentState(
                status=self._equipment_status(self._read_bool(elou, "ND2")),
                flow_kg_h=self._read_number(elou, "ND2_flow"),
            ),
            "H3": EquipmentState(
                status=self._equipment_status(self._read_bool(elou, "H3")),
                flow_kg_h=self._read_number(elou, "water_flow"),
            ),
            "E1": EquipmentState(
                status=self._equipment_status(self._read_bool(elou, "E1_voltage")),
                flow_kg_h=self._read_number(elou, "FQR118"),
            ),
        }

        return SimulationState(
            revision=revision,
            simulation_time_ms=revision * 1_000,
            boiler=oil_state.boiler,
            equipment=equipment,
            alarms=[*oil_state.alarms, *self._map_elou_alarms(elou)],
            process=process,
        )

    def _resolve_combined_revision(self, payload: dict[str, object]) -> int:
        if (
            self._combined_last_status_payload is not None
            and payload != self._combined_last_status_payload
        ):
            self._combined_revision += 1
        self._combined_last_status_payload = deepcopy(payload)
        return self._combined_revision

    @classmethod
    def _map_elou_alarms(cls, elou: dict[str, object]) -> list[Alarm]:
        alarms: list[Alarm] = []
        checks = (
            ("process_stopped", "KTC_ELOU_PROCESS_STOPPED", AlarmSeverity.CRITICAL, "stop_reason"),
            ("ND2_error", "KTC_ELOU_ND2_DOSING", AlarmSeverity.WARNING, None),
            ("E1_error", "KTC_ELOU_E1", AlarmSeverity.CRITICAL, None),
            ("H3_error", "KTC_ELOU_H3", AlarmSeverity.WARNING, None),
            ("PO1_error", "KTC_ELOU_PO1", AlarmSeverity.WARNING, None),
            ("KR7_error", "KTC_ELOU_KR7", AlarmSeverity.WARNING, None),
        )
        for field, code, severity, reason_field in checks:
            if not cls._read_optional_bool(elou, field):
                continue
            reason = elou.get(reason_field) if reason_field is not None else None
            alarms.append(
                Alarm(
                    code=code,
                    severity=severity,
                    message=str(reason) if reason else code,
                    active=True,
                )
            )
        return alarms
