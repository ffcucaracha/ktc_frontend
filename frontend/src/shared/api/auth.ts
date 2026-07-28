import { setAccessToken } from "../auth/authStore";
import { apiRequest, logoutRequest } from "./client";
import type { AccessTokenResponse, MeResponse, User } from "./types";

export interface LoginPayload {
  username: string;
  password: string;
}

export async function login(payload: LoginPayload): Promise<string> {
  const response = await apiRequest<AccessTokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
    retryOnUnauthorized: false,
  });
  setAccessToken(response.access_token);
  return response.access_token;
}

export async function getCurrentUser(): Promise<User> {
  const response = await apiRequest<MeResponse>("/auth/me", { auth: true });
  return response.user;
}

export async function logout(): Promise<void> {
  await logoutRequest();
}
