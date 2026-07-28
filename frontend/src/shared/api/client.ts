import { clearAccessToken, getAccessToken, setAccessToken } from "../auth/authStore";
import type { AccessTokenResponse, ApiErrorBody } from "./types";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

interface RequestOptions extends RequestInit {
  auth?: boolean;
  retryOnUnauthorized?: boolean;
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown>) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let refreshPromise: Promise<string> | null = null;

function buildUrl(path: string): string {
  return `${apiBaseUrl}${path}`;
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const { error } = value as { error: unknown };
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    "message" in error &&
    typeof (error as { code: unknown }).code === "string" &&
    typeof (error as { message: unknown }).message === "string"
  );
}

async function parseError(response: Response): Promise<ApiClientError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    return new ApiClientError(
      response.status,
      "HTTP_ERROR",
      "Сервер вернул неожиданный ответ",
      {},
    );
  }

  if (isApiErrorBody(payload)) {
    return new ApiClientError(
      response.status,
      payload.error.code,
      payload.error.message,
      payload.error.details,
    );
  }
  return new ApiClientError(response.status, "HTTP_ERROR", "Сервер вернул ошибку", {});
}

async function parseJson<TResponse>(response: Response): Promise<TResponse> {
  if (response.status === 204) {
    return undefined as TResponse;
  }
  return (await response.json()) as TResponse;
}

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise !== null) {
    return refreshPromise;
  }

  refreshPromise = fetch(buildUrl("/auth/refresh"), {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  })
    .then(async (response) => {
      if (!response.ok) {
        clearAccessToken();
        throw await parseError(response);
      }
      const payload = await parseJson<AccessTokenResponse>(response);
      setAccessToken(payload.access_token);
      return payload.access_token;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

export async function apiRequest<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const { auth = false, retryOnUnauthorized = true, headers, ...requestInit } = options;
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (requestInit.body !== undefined && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }

  const accessToken = getAccessToken();
  if (auth && accessToken !== null) {
    requestHeaders.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(buildUrl(path), {
    ...requestInit,
    credentials: "include",
    headers: requestHeaders,
  });

  if (response.status === 401 && auth && retryOnUnauthorized) {
    const nextAccessToken = await refreshAccessToken();
    return apiRequest<TResponse>(path, {
      ...options,
      headers: {
        ...Object.fromEntries(requestHeaders.entries()),
        Authorization: `Bearer ${nextAccessToken}`,
      },
      retryOnUnauthorized: false,
    });
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  return parseJson<TResponse>(response);
}

export async function logoutRequest(): Promise<void> {
  try {
    await apiRequest<void>("/auth/logout", {
      method: "POST",
      retryOnUnauthorized: false,
    });
  } finally {
    clearAccessToken();
  }
}
