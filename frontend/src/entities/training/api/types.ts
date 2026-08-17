export type OperatorErrorType = "WRONG_ACTION" | "LATE_ACTION" | "MISSED_ACTION" | "WRONG_SEQUENCE";

export interface OperatorError {
  id: string;
  session_id: string;
  scenario_expected_action_id: string | null;
  error_type: OperatorErrorType;
  severity: string;
  occurred_at_ms: number | null;
  evidence: Record<string, unknown>;
  causal_chain: Array<Record<string, unknown>>;
  source: "rule" | "ml";
  created_at: string;
}

export interface TrainingResult {
  id: string;
  session_id: string;
  scenario_id: string;
  score: number;
  max_score: number;
  reaction_time_ms: number | null;
  error_count: number;
  critical_error_count: number;
  sequence_score: number;
  reaction_score: number;
  safety_score: number;
  status: string;
  summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface TrainingAssessment {
  result: TrainingResult;
  errors: OperatorError[];
}

export interface RiskFeatureImportance {
  name: string;
  importance: number;
}

export interface RiskPrediction {
  risk: number;
  predicted_error_code: string | null;
  horizon_seconds: number;
  model_version: string;
  features: RiskFeatureImportance[];
}

export interface AICoachMessage {
  risk: number;
  title: string;
  reason: string;
  recommendation: string;
  predictedErrorCode: string | null;
  modelVersion: string;
  updatedAt: Date;
}

export interface ErrorExplanation {
  error_id: string;
  summary: string;
  explanation: string;
  recommendation: string;
  sources: Array<Record<string, unknown>>;
  model: string;
}

export interface SessionDebrief {
  session_id: string;
  status: string;
  generated_by: string;
  headline: string;
  strengths: string[];
  issues: string[];
  recommendations: string[];
  recommended_scenario_code: string | null;
  error_explanations: ErrorExplanation[];
}

export interface SimulationTimelineEvent {
  id: string;
  session_id: string;
  event_type: string;
  source: string;
  revision: number | null;
  simulation_time_ms: number | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface SimulationTimelineResponse {
  items: SimulationTimelineEvent[];
}

export interface TrainingResultListResponse {
  items: TrainingResult[];
}

export interface OperatorSkillProfile {
  operator_id: string;
  assessed_sessions: number;
  average_score: number | null;
  average_sequence_score: number | null;
  average_reaction_score: number | null;
  average_safety_score: number | null;
  error_counts: Record<string, number>;
  weakest_skill: string | null;
  recent_scores: number[];
}

export interface TrainingRecommendation {
  focus: string;
  priority: number;
  reason: string;
}

export interface TrainingRecommendationsResponse {
  operator_id: string;
  source: string;
  items: TrainingRecommendation[];
}

export type TrainingRealtimeEventType =
  | "assessment.error.detected"
  | "ai.risk.updated"
  | "ai.explanation.ready"
  | "training.result.ready";

export interface TrainingRealtimeEvent {
  type: TrainingRealtimeEventType;
  data: Record<string, unknown>;
}
