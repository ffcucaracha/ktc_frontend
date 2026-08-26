export type SimulationSessionStatus = "creating" | "active" | "stopping" | "completed" | "failed";
export type TrainingSessionMode = "training" | "exam";
export type TrainingScenarioDifficulty = "basic" | "medium" | "advanced";
export type EquipmentStatus =
  | "stopped"
  | "starting"
  | "running"
  | "stopping"
  | "fault"
  | "unavailable";
export type AlarmSeverity = "info" | "warning" | "critical";
export type SimulationEventType =
  | "session.ready"
  | "state.snapshot"
  | "state.patch"
  | "command.accepted"
  | "command.rejected"
  | "alarm.raised"
  | "alarm.cleared"
  | "integration.error"
  | "assessment.error.detected"
  | "ai.risk.updated"
  | "ai.explanation.ready"
  | "training.result.ready"
  | "session.completed"
  | "session.failed";

export interface SimulatorDefinition {
  id: string;
  code: string;
  external_id: string;
  name: string;
  description: string;
  visualization_type: string;
  is_active: boolean;
}

export interface SimulatorListResponse {
  items: SimulatorDefinition[];
}

export interface TrainingScenario {
  id: string;
  code: string;
  simulator_definition_id: string;
  name: string;
  description: string;
  difficulty: TrainingScenarioDifficulty;
  is_active: boolean;
  config: Record<string, unknown>;
}

export interface TrainingScenarioListResponse {
  items: TrainingScenario[];
}

export interface SimulationSession {
  id: string;
  operator_id: string;
  simulator_definition_id: string;
  training_scenario_id: string | null;
  mode: TrainingSessionMode;
  external_session_id: string | null;
  status: SimulationSessionStatus;
  started_at: string | null;
  ended_at: string | null;
  last_state: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateSimulationSessionPayload {
  simulator_id: string;
  scenario_id?: string;
  mode?: TrainingSessionMode;
}

export interface BoilerState {
  temperature_c: number;
  pressure_bar: number;
  status: string;
}

export interface EquipmentState {
  status: EquipmentStatus;
  flow_kg_h: number;
}

export interface Alarm {
  code: string;
  severity: AlarmSeverity;
  message: string;
  active: boolean;
}

export interface SimulationState {
  revision: number;
  simulation_time_ms: number;
  boiler: BoilerState;
  equipment: Record<string, EquipmentState>;
  alarms: Alarm[];
  process?: Record<string, unknown>;
}

export interface SimulationStateResponse {
  state: SimulationState;
}

export interface SimulationCommandPayload {
  command_id: string;
  equipment_id: string;
  action: "start" | "stop" | "set" | "open" | "close" | "reset" | "apply_voltage";
  payload: Record<string, unknown>;
  expected_revision?: number;
}

export interface SimulationCommandResponse {
  id: string;
  session_id: string;
  command_id: string;
  equipment_id: string;
  action: string;
  payload: Record<string, unknown>;
  status: "pending" | "accepted" | "rejected" | "failed";
  external_error_code: string | null;
  external_error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface SimulationEvent {
  type: SimulationEventType;
  data: Record<string, unknown>;
}
