import type { User } from "../../../shared/api/types";

export type Operator = User;

export interface OperatorListParams {
  limit: number;
  offset: number;
  username?: string;
  full_name?: string;
  is_active?: boolean;
}

export interface OperatorListResponse {
  items: Operator[];
  total: number;
  limit: number;
  offset: number;
}

export interface OperatorCreatePayload {
  username: string;
  full_name: string;
  password?: string;
}

export interface OperatorCreateResponse {
  operator: Operator;
  temporary_password: string | null;
}

export interface OperatorPatchPayload {
  username?: string;
  full_name?: string;
  is_active?: boolean;
}

export interface OperatorResetPasswordResponse {
  operator: Operator;
  temporary_password: string;
}

export interface LoginStats {
  successful_count: number;
  last_successful_login_at: string | null;
}

export interface LoginHistoryItem {
  id: string;
  occurred_at: string;
  success: boolean;
  failure_reason: "invalid_credentials" | "inactive_user" | null;
  ip_address: string | null;
  user_agent: string | null;
}

export interface LoginHistoryResponse {
  items: LoginHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}
