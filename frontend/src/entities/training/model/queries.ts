import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import {
  getSessionDebrief,
  getSessionTimeline,
  getTrainingAssessment,
} from "../api/trainingApi";
import type {
  SessionDebrief,
  SimulationTimelineEvent,
  TrainingAssessment,
} from "../api/types";

export const trainingQueryKey = ["training"] as const;

export function useTrainingAssessmentQuery(
  sessionId: string,
  enabled = true,
): UseQueryResult<TrainingAssessment> {
  return useQuery({
    queryKey: [...trainingQueryKey, sessionId, "assessment"],
    queryFn: () => getTrainingAssessment(sessionId),
    enabled: enabled && sessionId.length > 0,
  });
}

export function useSessionDebriefQuery(
  sessionId: string,
  enabled = true,
): UseQueryResult<SessionDebrief> {
  return useQuery({
    queryKey: [...trainingQueryKey, sessionId, "debrief"],
    queryFn: () => getSessionDebrief(sessionId),
    enabled: enabled && sessionId.length > 0,
  });
}

export function useSessionTimelineQuery(
  sessionId: string,
  enabled = true,
): UseQueryResult<SimulationTimelineEvent[]> {
  return useQuery({
    queryKey: [...trainingQueryKey, sessionId, "timeline"],
    queryFn: () => getSessionTimeline(sessionId),
    enabled: enabled && sessionId.length > 0,
  });
}
