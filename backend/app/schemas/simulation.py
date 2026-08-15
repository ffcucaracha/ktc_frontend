from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    SimulationCommandStatus,
    SimulationSessionStatus,
    TrainingScenarioDifficulty,
    TrainingSessionMode,
)


class SimulatorResponse(BaseModel):
    id: UUID
    code: str
    external_id: str
    name: str
    description: str
    visualization_type: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SimulatorListResponse(BaseModel):
    items: list[SimulatorResponse]


class TrainingScenarioResponse(BaseModel):
    id: UUID
    code: str
    simulator_definition_id: UUID
    name: str
    description: str
    difficulty: TrainingScenarioDifficulty
    is_active: bool
    config: dict[str, object]

    model_config = ConfigDict(from_attributes=True)


class TrainingScenarioListResponse(BaseModel):
    items: list[TrainingScenarioResponse]


class SimulationSessionCreateRequest(BaseModel):
    simulator_id: UUID
    scenario_id: UUID | None = None
    mode: TrainingSessionMode = TrainingSessionMode.TRAINING


class SimulationSessionResponse(BaseModel):
    id: UUID
    operator_id: UUID
    simulator_definition_id: UUID
    training_scenario_id: UUID | None
    mode: TrainingSessionMode
    external_session_id: str | None
    status: SimulationSessionStatus
    started_at: datetime | None
    ended_at: datetime | None
    last_state: dict[str, object] | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SimulationStateResponse(BaseModel):
    state: dict[str, object]


class SimulationCommandRequest(BaseModel):
    command_id: UUID
    equipment_id: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=50)
    payload: dict[str, object] = Field(default_factory=dict)
    expected_revision: int | None = Field(default=None, ge=0)


class SimulationCommandResponse(BaseModel):
    id: UUID
    session_id: UUID
    command_id: UUID
    equipment_id: str
    action: str
    payload: dict[str, object]
    status: SimulationCommandStatus
    external_error_code: str | None
    external_error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
