import { useQuery } from "@tanstack/react-query";

import { listAiModels } from "../api/modelsApi";

export const aiModelsQueryKey = ["admin", "ai-models"] as const;

export function useAiModelsQuery() {
  return useQuery({
    queryKey: aiModelsQueryKey,
    queryFn: listAiModels,
  });
}
