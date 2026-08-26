from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OperatorProfile(BaseModel):
    previous_errors: dict[str, int] = Field(default_factory=dict)


class TelemetryPoint(BaseModel):
    simulation_time_ms: int
    revision: int
    sensors: dict[str, float] = Field(default_factory=dict)
    pumps: dict[str, bool] = Field(default_factory=dict)
    valves: dict[str, bool] = Field(default_factory=dict)
    regulators: dict[str, float | int] = Field(default_factory=dict)
    dosing: dict[str, Any] = Field(default_factory=dict)
    elou: dict[str, Any] = Field(default_factory=dict)
    alarms: list[dict[str, Any]] = Field(default_factory=list)


class RecentAction(BaseModel):
    simulation_time_ms: int | None = None
    equipment_id: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class FeatureImportance(BaseModel):
    name: str
    importance: float


class RiskPredictionRequest(BaseModel):
    session_id: UUID
    scenario_code: str
    operator_profile: OperatorProfile = Field(default_factory=OperatorProfile)
    window: list[TelemetryPoint] = Field(default_factory=list)
    recent_actions: list[RecentAction] = Field(default_factory=list)


class RiskPrediction(BaseModel):
    risk: float = Field(ge=0.0, le=1.0)
    predicted_error_code: str | None
    horizon_seconds: int = Field(gt=0)
    model_version: str
    decision_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    features: list[FeatureImportance] = Field(default_factory=list)


class ErrorExplanationRequest(BaseModel):
    error_code: str
    severity: str
    expected_action: dict[str, Any] | None = None
    actual_action: dict[str, Any] | None = None
    process_context: dict[str, Any] = Field(default_factory=dict)
    cause: list[dict[str, Any]] = Field(default_factory=list)
    consequences: list[dict[str, Any]] = Field(default_factory=list)
    regulation_context: list[dict[str, Any]] = Field(default_factory=list)


class ErrorExplanation(BaseModel):
    summary: str
    explanation: str
    recommendation: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    model: str


class DebriefError(BaseModel):
    error_code: str
    severity: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class DebriefRequest(BaseModel):
    session_id: UUID
    session_result: dict[str, Any]
    errors: list[DebriefError] = Field(default_factory=list)
    reaction_metrics: dict[str, Any] = Field(default_factory=dict)
    operator_skill_profile: dict[str, Any] = Field(default_factory=dict)
    scenario_metadata: dict[str, Any] = Field(default_factory=dict)


class Debrief(BaseModel):
    short_summary: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    priority_actions: list[str] = Field(default_factory=list)
    recommended_scenario_code: str | None = None
    model: str


class RecommendationRequest(BaseModel):
    operator_id: UUID
    skill_profile: dict[str, Any] = Field(default_factory=dict)
    previous_errors: dict[str, int] = Field(default_factory=dict)
    available_scenarios: list[dict[str, Any]] = Field(default_factory=list)


class Recommendation(BaseModel):
    recommended_scenario_code: str | None = None
    rationale: str
    priority: str = "medium"
    model: str
