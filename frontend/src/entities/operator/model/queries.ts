import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createOperator,
  getOperator,
  getOperatorLoginHistory,
  getOperatorLoginStats,
  listOperators,
  patchOperator,
  resetOperatorPassword,
} from "../api/operatorsApi";
import type {
  LoginStats,
  OperatorCreatePayload,
  OperatorListParams,
  OperatorPatchPayload,
} from "../api/types";

export const operatorsQueryKey = ["operators"] as const;

export function useOperatorsQuery(params: OperatorListParams) {
  return useQuery({
    queryKey: [...operatorsQueryKey, "list", params],
    queryFn: () => listOperators(params),
  });
}

export function useOperatorStatsQueries(operatorIds: string[]) {
  return useQueries({
    queries: operatorIds.map((operatorId) => ({
      queryKey: [...operatorsQueryKey, operatorId, "stats"],
      queryFn: () => getOperatorLoginStats(operatorId),
      enabled: operatorId.length > 0,
    })),
  });
}

export function useOperatorQuery(operatorId: string) {
  return useQuery({
    queryKey: [...operatorsQueryKey, operatorId, "detail"],
    queryFn: () => getOperator(operatorId),
    enabled: operatorId.length > 0,
  });
}

export function useOperatorStatsQuery(operatorId: string) {
  return useQuery<LoginStats>({
    queryKey: [...operatorsQueryKey, operatorId, "stats"],
    queryFn: () => getOperatorLoginStats(operatorId),
    enabled: operatorId.length > 0,
  });
}

export function useOperatorLoginHistoryQuery(operatorId: string, limit: number, offset: number) {
  return useQuery({
    queryKey: [...operatorsQueryKey, operatorId, "history", { limit, offset }],
    queryFn: () => getOperatorLoginHistory(operatorId, limit, offset),
    enabled: operatorId.length > 0,
  });
}

export function useCreateOperatorMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OperatorCreatePayload) => createOperator(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: operatorsQueryKey });
    },
  });
}

export function usePatchOperatorMutation(operatorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OperatorPatchPayload) => patchOperator(operatorId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: operatorsQueryKey });
    },
  });
}

export function useResetOperatorPasswordMutation(operatorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => resetOperatorPassword(operatorId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: operatorsQueryKey });
    },
  });
}
