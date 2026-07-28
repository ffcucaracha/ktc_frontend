from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BoilerStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    FAULT = "fault"
    UNAVAILABLE = "unavailable"


class EquipmentStatus(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAULT = "fault"
    UNAVAILABLE = "unavailable"


class AlarmSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class CommandStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SimulationEventType(StrEnum):
    SESSION_READY = "session.ready"
    STATE_SNAPSHOT = "state.snapshot"
    STATE_PATCH = "state.patch"
    COMMAND_ACCEPTED = "command.accepted"
    COMMAND_REJECTED = "command.rejected"
    ALARM_RAISED = "alarm.raised"
    ALARM_CLEARED = "alarm.cleared"
    INTEGRATION_ERROR = "integration.error"
    SESSION_COMPLETED = "session.completed"
    SESSION_FAILED = "session.failed"


class BoilerState(BaseModel):
    temperature_c: float
    pressure_bar: float
    status: BoilerStatus


class EquipmentState(BaseModel):
    status: EquipmentStatus
    flow_kg_h: float


class Alarm(BaseModel):
    code: str
    severity: AlarmSeverity
    message: str
    active: bool


class SimulationState(BaseModel):
    revision: int = Field(ge=0)
    simulation_time_ms: int = Field(ge=0)
    boiler: BoilerState
    equipment: dict[str, EquipmentState]
    alarms: list[Alarm]
    process: dict[str, object] = Field(default_factory=dict)


class ExternalSession(BaseModel):
    session_id: str
    status: str
    state: SimulationState | None = None


class CommandResult(BaseModel):
    command_id: UUID
    status: CommandStatus
    code: str | None = None
    message: str | None = None


class SimulationEvent(BaseModel):
    type: SimulationEventType
    data: dict[str, object]

    model_config = ConfigDict(extra="forbid")
