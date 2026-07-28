import json

from pydantic import ValidationError

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
from app.integrations.simulation.errors import InvalidExternalPayloadError
from app.integrations.simulation.external_dto import (
    ExternalAlarm,
    ExternalBoilerState,
    ExternalCommandResponse,
    ExternalCreateSessionResponse,
    ExternalEquipmentState,
    ExternalEvent,
    ExternalSimulationState,
)


def map_boiler_status(value: str) -> BoilerStatus:
    try:
        return BoilerStatus(value)
    except ValueError as exc:
        raise InvalidExternalPayloadError from exc


def map_equipment_status(value: str) -> EquipmentStatus:
    try:
        return EquipmentStatus(value)
    except ValueError as exc:
        raise InvalidExternalPayloadError from exc


def map_alarm_severity(value: str) -> AlarmSeverity:
    try:
        return AlarmSeverity(value)
    except ValueError as exc:
        raise InvalidExternalPayloadError from exc


def map_event_type(value: str) -> SimulationEventType:
    try:
        return SimulationEventType(value)
    except ValueError as exc:
        raise InvalidExternalPayloadError from exc


def map_boiler_state(external: ExternalBoilerState) -> BoilerState:
    return BoilerState(
        temperature_c=external.temperature_c,
        pressure_bar=external.pressure_bar,
        status=map_boiler_status(external.status),
    )


def map_equipment_state(external: ExternalEquipmentState) -> EquipmentState:
    return EquipmentState(
        status=map_equipment_status(external.status),
        flow_kg_h=external.flow_kg_h,
    )


def map_alarm(external: ExternalAlarm) -> Alarm:
    return Alarm(
        code=external.code,
        severity=map_alarm_severity(external.severity),
        message=external.message,
        active=external.active,
    )


def map_state(external: ExternalSimulationState) -> SimulationState:
    return SimulationState(
        revision=external.revision,
        simulation_time_ms=external.simulation_time_ms,
        boiler=map_boiler_state(external.boiler),
        equipment={
            equipment_id: map_equipment_state(equipment)
            for equipment_id, equipment in external.equipment.items()
        },
        alarms=[map_alarm(alarm) for alarm in external.alarms],
    )


def parse_external_state(payload: object) -> SimulationState:
    try:
        return map_state(ExternalSimulationState.model_validate(payload))
    except ValidationError as exc:
        raise InvalidExternalPayloadError from exc


def parse_external_session(payload: object) -> ExternalSession:
    try:
        external = ExternalCreateSessionResponse.model_validate(payload)
    except ValidationError as exc:
        raise InvalidExternalPayloadError from exc
    return ExternalSession(
        session_id=external.session_id,
        status=external.status,
        state=map_state(external.state) if external.state is not None else None,
    )


def parse_external_command_result(payload: object) -> CommandResult:
    try:
        external = ExternalCommandResponse.model_validate(payload)
    except ValidationError as exc:
        raise InvalidExternalPayloadError from exc
    return CommandResult(
        command_id=external.command_id,
        status=CommandStatus(external.status),
        code=external.code,
        message=external.message,
    )


def parse_external_event(payload: object) -> SimulationEvent:
    try:
        external = ExternalEvent.model_validate(payload)
    except ValidationError as exc:
        raise InvalidExternalPayloadError from exc
    return SimulationEvent(type=map_event_type(external.type), data=external.data)


def parse_external_event_json(payload: str | bytes) -> SimulationEvent:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise InvalidExternalPayloadError from exc
    return parse_external_event(decoded)
