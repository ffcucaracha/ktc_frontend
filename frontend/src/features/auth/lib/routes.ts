import type { UserRole } from "../../../shared/api/types";

export function homePathForRole(role: UserRole): string {
  return role === "admin" ? "/admin/operators" : "/operator/simulators";
}
