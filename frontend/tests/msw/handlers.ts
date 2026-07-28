import { http, HttpResponse } from "msw";

import type { AccessTokenResponse, ApiErrorBody, MeResponse, User } from "../../src/shared/api/types";

export const apiBaseUrl = "http://localhost:8000/api/v1";

export const adminUser: User = {
  id: "8ab879d9-0ec2-4234-8f5a-59391f385ae2",
  username: "admin",
  full_name: "Администратор",
  role: "admin",
  is_active: true,
};

export const operatorUser: User = {
  id: "9df86a3d-af5f-4b6d-8901-bec7e6361fdd",
  username: "operator",
  full_name: "Оператор",
  role: "operator",
  is_active: true,
};

export function apiError(status: number, code: string, message: string): HttpResponse<ApiErrorBody> {
  return HttpResponse.json(
    {
      error: {
        code,
        message,
        details: {},
      },
    },
    { status },
  );
}

export function tokenResponse(accessToken: string): HttpResponse<AccessTokenResponse> {
  return HttpResponse.json({
    access_token: accessToken,
    token_type: "bearer",
  });
}

export function meResponse(user: User): HttpResponse<MeResponse> {
  return HttpResponse.json({ user });
}

export const handlers = [
  http.get(`${apiBaseUrl}/auth/me`, () =>
    apiError(401, "UNAUTHENTICATED", "Требуется вход в систему"),
  ),
  http.post(`${apiBaseUrl}/auth/refresh`, () =>
    apiError(401, "UNAUTHENTICATED", "Требуется вход в систему"),
  ),
  http.post(`${apiBaseUrl}/auth/login`, () =>
    apiError(401, "INVALID_CREDENTIALS", "Неверное имя пользователя или пароль"),
  ),
  http.post(`${apiBaseUrl}/auth/logout`, () => new HttpResponse(null, { status: 204 })),
  http.get(`${apiBaseUrl}/operators`, () =>
    HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
  ),
  http.get(`${apiBaseUrl}/simulators`, () =>
    HttpResponse.json({
      items: [
        {
          id: "0edfd69d-1353-40aa-a818-037952a46534",
          code: "boiler-demo",
          external_id: "boiler-001",
          name: "Котёл с двумя насосами",
          description: "Демонстрационная установка",
          visualization_type: "boiler-v1",
          is_active: true,
        },
      ],
    }),
  ),
];
