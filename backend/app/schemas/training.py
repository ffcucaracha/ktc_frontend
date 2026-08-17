from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import OperatorErrorSource, OperatorErrorType


class SimulationTimelineEventResponse(BaseModel):
    id: UUID
    session_id: UUID
    event_type: str
    source: str
    revision: int | None
    simulation_time_ms: int | None
    payload: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SimulationTimelineResponse(BaseModel):
    items: list[SimulationTimelineEventResponse]


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


class OperatorErrorsResponse(BaseModel):
    items: list[OperatorErrorResponse]


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


class TrainingResultListResponse(BaseModel):
    items: list[TrainingResultResponse]


class SkillProfileResponse(BaseModel):
    operator_id: UUID
    assessed_sessions: int
    average_score: float | None
    average_sequence_score: float | None
    average_reaction_score: float | None
    average_safety_score: float | None
    error_counts: dict[str, int]
    weakest_skill: str | None
    recent_scores: list[float]


class TrainingRecommendationResponse(BaseModel):
    focus: str
    priority: int
    reason: str
    scenario_id: UUID | None = None
    scenario_code: str | None = None
    scenario_name: str | None = None


class TrainingRecommendationsResponse(BaseModel):
    operator_id: UUID
    source: str
    items: list[TrainingRecommendationResponse]


class ErrorExplanationResponse(BaseModel):
    error_id: UUID
    summary: str
    explanation: str
    recommendation: str
    sources: list[dict[str, object]] = Field(default_factory=list)
    model: str


class DebriefResponse(BaseModel):
    session_id: UUID
    status: str
    generated_by: str
    headline: str
    strengths: list[str]
    issues: list[str]
    recommendations: list[str]
    recommended_scenario_code: str | None = None
    error_explanations: list[ErrorExplanationResponse] = Field(default_factory=list)
