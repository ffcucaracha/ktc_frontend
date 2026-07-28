from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ExternalBoilerState(BaseModel):
    temperature_c: float
    pressure_bar: float
    status: str


class ExternalEquipmentState(BaseModel):
    status: str
    flow_kg_h: float


class ExternalAlarm(BaseModel):
    code: str
    severity: str
    message: str
    active: bool


class ExternalSimulationState(BaseModel):
    revision: int = Field(ge=0)
    simulation_time_ms: int = Field(ge=0)
    boiler: ExternalBoilerState
    equipment: dict[str, ExternalEquipmentState]
    alarms: list[ExternalAlarm]


class ExternalCreateSessionResponse(BaseModel):
    session_id: str
    status: str
    state: ExternalSimulationState | None = None


class ExternalCommandResponse(BaseModel):
    command_id: UUID
    status: Literal["accepted", "rejected"]
    code: str | None = None
    message: str | None = None


class ExternalEvent(BaseModel):
    type: str
    data: dict[str, object]
