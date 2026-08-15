from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import OperatorErrorSource, OperatorErrorType


class OperatorErrorResponse(BaseModel):
    id: UUID
    session_id: UUID
    scenario_expected_action_id: UUID | None
    error_type: OperatorErrorType
    severity: str
    occurred_at_ms: int | None
    evidence: dict[str, object]
    causal_chain: list[dict[str, object]]
    source: OperatorErrorSource
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingResultResponse(BaseModel):
    id: UUID
    session_id: UUID
    scenario_id: UUID
    score: float
    max_score: float
    reaction_time_ms: int | None
    error_count: int
    critical_error_count: int
    sequence_score: float
    reaction_score: float
    safety_score: float
    status: str
    summary: dict[str, object]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingAssessmentResponse(BaseModel):
    result: TrainingResultResponse
    errors: list[OperatorErrorResponse]
