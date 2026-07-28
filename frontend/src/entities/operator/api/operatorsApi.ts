import { apiRequest } from "../../../shared/api/client";
import type {
  LoginHistoryResponse,
  LoginStats,
  Operator,
  OperatorCreatePayload,
  OperatorCreateResponse,
  OperatorListParams,
  OperatorListResponse,
  OperatorPatchPayload,
  OperatorResetPasswordResponse,
} from "./types";

function appendOptionalParam(
  params: URLSearchParams,
  key: string,
  value: string | number | boolean | undefined,
): void {
  if (value !== undefined && value !== "") {
    params.set(key, String(value));
  }
}

export async function listOperators(params: OperatorListParams): Promise<OperatorListResponse> {
  const searchParams = new URLSearchParams();
  appendOptionalParam(searchParams, "limit", params.limit);
  appendOptionalParam(searchParams, "offset", params.offset);
  appendOptionalParam(searchParams, "username", params.username);
  appendOptionalParam(searchParams, "full_name", params.full_name);
  appendOptionalParam(searchParams, "is_active", params.is_active);

  return apiRequest<OperatorListResponse>(`/operators?${searchParams.toString()}`, {
    auth: true,
  });
}

export async function createOperator(
  payload: OperatorCreatePayload,
): Promise<OperatorCreateResponse> {
  return apiRequest<OperatorCreateResponse>("/operators", {
    method: "POST",
    auth: true,
    body: JSON.stringify(payload),
  });
}

export async function getOperator(operatorId: string): Promise<Operator> {
  return apiRequest<Operator>(`/operators/${operatorId}`, { auth: true });
}

export async function patchOperator(
  operatorId: string,
  payload: OperatorPatchPayload,
): Promise<Operator> {
  return apiRequest<Operator>(`/operators/${operatorId}`, {
    method: "PATCH",
    auth: true,
    body: JSON.stringify(payload),
  });
}

export async function resetOperatorPassword(
  operatorId: string,
): Promise<OperatorResetPasswordResponse> {
  return apiRequest<OperatorResetPasswordResponse>(`/operators/${operatorId}/reset-password`, {
    method: "POST",
    auth: true,
  });
}

export async function getOperatorLoginStats(operatorId: string): Promise<LoginStats> {
  return apiRequest<LoginStats>(`/operators/${operatorId}/login-stats`, { auth: true });
}

export async function getOperatorLoginHistory(
  operatorId: string,
  limit: number,
  offset: number,
): Promise<LoginHistoryResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set("limit", String(limit));
  searchParams.set("offset", String(offset));
  return apiRequest<LoginHistoryResponse>(
    `/operators/${operatorId}/login-history?${searchParams.toString()}`,
    { auth: true },
  );
}
