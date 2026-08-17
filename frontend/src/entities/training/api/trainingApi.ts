import { apiRequest } from "../../../shared/api/client";
import { getAccessToken } from "../../../shared/auth/authStore";
import type {
  OperatorSkillProfile,
  SessionDebrief,
  SimulationTimelineEvent,
  SimulationTimelineResponse,
  TrainingAssessment,
  TrainingRecommendationsResponse,
  TrainingResult,
  TrainingResultListResponse,
} from "./types";

export async function getTrainingAssessment(sessionId: string): Promise<TrainingAssessment> {
  return apiRequest<TrainingAssessment>(`/simulation-sessions/${sessionId}/assessment`, {
    auth: true,
  });
}

export async function getSessionDebrief(sessionId: string): Promise<SessionDebrief> {
  return apiRequest<SessionDebrief>(`/simulation-sessions/${sessionId}/debrief`, {
    auth: true,
  });
}

export async function getSessionTimeline(sessionId: string): Promise<SimulationTimelineEvent[]> {
  const response = await apiRequest<SimulationTimelineResponse>(
    `/simulation-sessions/${sessionId}/timeline`,
    { auth: true },
  );
  return response.items;
}

export async function getOperatorTrainingResults(operatorId: string): Promise<TrainingResult[]> {
  const response = await apiRequest<TrainingResultListResponse>(
    `/operators/${operatorId}/training-results`,
    { auth: true },
  );
  return response.items;
}

export async function getOperatorSkillProfile(operatorId: string): Promise<OperatorSkillProfile> {
  return apiRequest<OperatorSkillProfile>(`/operators/${operatorId}/skill-profile`, { auth: true });
}

export async function getOperatorRecommendations(
  operatorId: string,
): Promise<TrainingRecommendationsResponse> {
  return apiRequest<TrainingRecommendationsResponse>(`/operators/${operatorId}/recommendations`, {
    auth: true,
  });
}

export function createTrainingEventSocket(sessionId: string): WebSocket {
  const accessToken = getAccessToken();
  if (accessToken === null) {
    throw new Error("Access token is required for training WebSocket");
  }
  const baseUrl = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000/ws/v1";
  const url = new URL(`${baseUrl}/simulation-sessions/${sessionId}/training`);
  url.searchParams.set("access_token", accessToken);
  return new WebSocket(url);
}
