import { useMutation, useQuery } from "@tanstack/react-query";

import {
  createSimulationSession,
  getSimulationSession,
  getSimulationState,
  getSimulator,
  listSimulators,
  stopSimulationSession,
} from "../api/simulationApi";
import type { CreateSimulationSessionPayload } from "../api/types";

export const simulatorsQueryKey = ["simulators"] as const;
export const simulationSessionsQueryKey = ["simulation-sessions"] as const;

export function useSimulatorsQuery() {
  return useQuery({
    queryKey: [...simulatorsQueryKey, "list"],
    queryFn: listSimulators,
  });
}

export function useSimulatorQuery(simulatorId: string) {
  return useQuery({
    queryKey: [...simulatorsQueryKey, simulatorId],
    queryFn: () => getSimulator(simulatorId),
    enabled: simulatorId.length > 0,
  });
}

export function useCreateSimulationSessionMutation() {
  return useMutation({
    mutationFn: (payload: CreateSimulationSessionPayload) => createSimulationSession(payload),
  });
}

export function useSimulationSessionQuery(sessionId: string) {
  return useQuery({
    queryKey: [...simulationSessionsQueryKey, sessionId],
    queryFn: () => getSimulationSession(sessionId),
    enabled: sessionId.length > 0,
  });
}

export function useSimulationStateQuery(sessionId: string) {
  return useQuery({
    queryKey: [...simulationSessionsQueryKey, sessionId, "state"],
    queryFn: () => getSimulationState(sessionId),
    enabled: sessionId.length > 0,
  });
}

export function useStopSimulationSessionMutation() {
  return useMutation({
    mutationFn: (sessionId: string) => stopSimulationSession(sessionId),
  });
}
