import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import {
  getOperatorRecommendations,
  getOperatorSkillProfile,
  getOperatorTrainingResults,
  getSessionDebrief,
  getSessionTimeline,
  getTrainingAssessment,
} from "../api/trainingApi";
import type {
  OperatorSkillProfile,
  SessionDebrief,
  SimulationTimelineEvent,
  TrainingAssessment,
  TrainingRecommendationsResponse,
  TrainingResult,
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

export function useOperatorTrainingResultsQuery(
  operatorId: string,
): UseQueryResult<TrainingResult[]> {
  return useQuery({
    queryKey: [...trainingQueryKey, "operator", operatorId, "results"],
    queryFn: () => getOperatorTrainingResults(operatorId),
    enabled: operatorId.length > 0,
  });
}

export function useOperatorSkillProfileQuery(
  operatorId: string,
): UseQueryResult<OperatorSkillProfile> {
  return useQuery({
    queryKey: [...trainingQueryKey, "operator", operatorId, "skill-profile"],
    queryFn: () => getOperatorSkillProfile(operatorId),
    enabled: operatorId.length > 0,
  });
}

export function useOperatorRecommendationsQuery(
  operatorId: string,
): UseQueryResult<TrainingRecommendationsResponse> {
  return useQuery({
    queryKey: [...trainingQueryKey, "operator", operatorId, "recommendations"],
    queryFn: () => getOperatorRecommendations(operatorId),
    enabled: operatorId.length > 0,
  });
}
