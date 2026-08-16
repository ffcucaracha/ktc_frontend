import { apiRequest } from "../../../shared/api/client";
import { getAccessToken } from "../../../shared/auth/authStore";
import type { SessionDebrief, TrainingAssessment } from "./types";

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
