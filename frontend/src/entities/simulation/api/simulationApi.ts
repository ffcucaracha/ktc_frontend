import { apiRequest } from "../../../shared/api/client";
import type {
  CreateSimulationSessionPayload,
  SimulationCommandPayload,
  SimulationCommandResponse,
  SimulationSession,
  SimulationState,
  SimulationStateResponse,
  SimulatorDefinition,
  SimulatorListResponse,
  TrainingScenario,
  TrainingScenarioListResponse,
} from "./types";

export async function listSimulators(): Promise<SimulatorDefinition[]> {
  const response = await apiRequest<SimulatorListResponse>("/simulators", { auth: true });
  return response.items;
}

export async function getSimulator(simulatorId: string): Promise<SimulatorDefinition> {
  return apiRequest<SimulatorDefinition>(`/simulators/${simulatorId}`, { auth: true });
}

export async function listTrainingScenarios(simulatorId: string): Promise<TrainingScenario[]> {
  const response = await apiRequest<TrainingScenarioListResponse>(
    `/simulators/${simulatorId}/scenarios`,
    { auth: true },
  );
  return response.items;
}

export async function createSimulationSession(
  payload: CreateSimulationSessionPayload,
): Promise<SimulationSession> {
  return apiRequest<SimulationSession>("/simulation-sessions", {
    method: "POST",
    auth: true,
    body: JSON.stringify(payload),
  });
}

export async function getSimulationSession(sessionId: string): Promise<SimulationSession> {
  return apiRequest<SimulationSession>(`/simulation-sessions/${sessionId}`, { auth: true });
}

export async function getSimulationState(sessionId: string): Promise<SimulationState> {
  const response = await apiRequest<SimulationStateResponse>(
    `/simulation-sessions/${sessionId}/state`,
    { auth: true },
  );
  return response.state;
}

export async function sendSimulationCommand(
  sessionId: string,
  payload: SimulationCommandPayload,
): Promise<SimulationCommandResponse> {
  return apiRequest<SimulationCommandResponse>(`/simulation-sessions/${sessionId}/commands`, {
    method: "POST",
    auth: true,
    body: JSON.stringify(payload),
  });
}

export async function stopSimulationSession(sessionId: string): Promise<SimulationSession> {
  return apiRequest<SimulationSession>(`/simulation-sessions/${sessionId}/stop`, {
    method: "POST",
    auth: true,
  });
}
