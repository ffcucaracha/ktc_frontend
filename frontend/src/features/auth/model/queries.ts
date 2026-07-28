import { useQuery } from "@tanstack/react-query";

import { getCurrentUser } from "../../../shared/api/auth";
import type { User } from "../../../shared/api/types";

export const currentUserQueryKey = ["auth", "me"] as const;

export function useCurrentUserQuery() {
  return useQuery<User>({
    queryKey: currentUserQueryKey,
    queryFn: getCurrentUser,
    retry: false,
    staleTime: 60_000,
  });
}
