import { http, HttpResponse } from "msw";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { setAccessToken } from "../shared/auth/authStore";
import { App } from "./App";
import {
  adminUser,
  apiBaseUrl,
  apiError,
  meResponse,
  operatorUser,
  tokenResponse,
} from "../../tests/msw/handlers";
import { server } from "../../tests/msw/server";
import type { LoginHistoryResponse, LoginStats, OperatorListResponse } from "../entities/operator/api/types";
import type { ApiErrorBody, MeResponse, User } from "../shared/api/types";
import type { EquipmentStatus, SimulationState } from "../entities/simulation/api/types";

type AuthMeMockResponse = ApiErrorBody | MeResponse;

function renderAt(path: string): void {
  window.history.pushState(null, "", path);
  render(<App />);
}

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  readonly url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    window.setTimeout(() => this.onopen?.(), 0);
  }

  close(): void {
    this.onclose?.();
  }

  emit(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }

  emitRaw(data: string): void {
    this.onmessage?.({ data } as MessageEvent<string>);
  }

  serverClose(): void {
    this.onclose?.();
  }
}

function installMockWebSocket(): void {
  MockWebSocket.instances = [];
  globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket;
}

function authMeResponse(user: User): HttpResponse<AuthMeMockResponse> {
  return meResponse(user) as HttpResponse<AuthMeMockResponse>;
}

function unauthenticatedResponse(): HttpResponse<AuthMeMockResponse> {
  return apiError(401, "UNAUTHENTICATED", "Требуется вход в систему") as HttpResponse<AuthMeMockResponse>;
}

function useAdminSession(): void {
  setAccessToken("admin-token");
  server.use(
    http.get(`${apiBaseUrl}/auth/me`, ({ request }) => {
      if (request.headers.get("Authorization") === "Bearer admin-token") {
        return authMeResponse(adminUser);
      }
      return unauthenticatedResponse();
    }),
  );
}

function useOperatorSession(): void {
  setAccessToken("operator-token");
  server.use(
    http.get(`${apiBaseUrl}/auth/me`, ({ request }) => {
      if (request.headers.get("Authorization") === "Bearer operator-token") {
        return authMeResponse(operatorUser);
      }
      return unauthenticatedResponse();
    }),
  );
}

function operatorListResponse(items: User[]): OperatorListResponse {
  return {
    items,
    total: items.length,
    limit: 10,
    offset: 0,
  };
}

function loginStatsResponse(count: number, lastLogin: string | null): LoginStats {
  return {
    successful_count: count,
    last_successful_login_at: lastLogin,
  };
}

function boilerState(
  revision: number,
  supply: EquipmentStatus = "stopped",
  exhaust: EquipmentStatus = "stopped",
): SimulationState {
  return {
    revision,
    simulation_time_ms: revision * 1_000,
    boiler: {
      temperature_c: 100 + revision,
      pressure_bar: 1 + revision / 10,
      status: "idle",
    },
    equipment: {
      steam_supply_pump: { status: supply, flow_kg_h: 0 },
      steam_exhaust_pump: { status: exhaust, flow_kg_h: 0 },
    },
    alarms: [],
  };
}

function sessionResponse() {
  return {
    id: "37e020cf-0e03-4654-bef5-09b020210b22",
    operator_id: operatorUser.id,
    simulator_definition_id: "0edfd69d-1353-40aa-a818-037952a46534",
    external_session_id: "external-session-1",
    status: "active",
    started_at: "2026-07-13T05:00:00Z",
    ended_at: null,
    last_state: null,
    error_code: null,
    error_message: null,
    created_at: "2026-07-13T05:00:00Z",
    updated_at: "2026-07-13T05:00:00Z",
  };
}

function useSessionHandlers(initialState: SimulationState = boilerState(1)): void {
  server.use(
    http.get(`${apiBaseUrl}/simulation-sessions/:sessionId`, () => HttpResponse.json(sessionResponse())),
    http.get(`${apiBaseUrl}/simulation-sessions/:sessionId/state`, () =>
      HttpResponse.json({ state: initialState }),
    ),
  );
}

async function readJsonObject(request: Request): Promise<Record<string, unknown>> {
  const payload: unknown = await request.json();
  if (typeof payload === "object" && payload !== null && !Array.isArray(payload)) {
    return payload as Record<string, unknown>;
  }
  return {};
}

function readStringField(payload: Record<string, unknown>, field: string): string {
  const value = payload[field];
  return typeof value === "string" ? value : "";
}

describe("auth flow", () => {
  it("logs in and redirects admin to operators", async () => {
    server.use(
      http.post(`${apiBaseUrl}/auth/login`, () => tokenResponse("admin-token")),
      http.get(`${apiBaseUrl}/auth/me`, ({ request }) => {
        if (request.headers.get("Authorization") === "Bearer admin-token") {
          return authMeResponse(adminUser);
        }
        return unauthenticatedResponse();
      }),
    );

    renderAt("/login");

    await userEvent.type(await screen.findByLabelText("Имя пользователя"), "admin");
    await userEvent.type(screen.getByLabelText("Пароль"), "secret-password");
    await userEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("heading", { name: "Операторы" })).toBeVisible();
    expect(window.location.pathname).toBe("/admin/operators");
  });

  it("logs in with the e2e admin shortcut", async () => {
    let loginPayload: Record<string, unknown> | null = null;
    server.use(
      http.post(`${apiBaseUrl}/auth/login`, async ({ request }) => {
        loginPayload = await readJsonObject(request);
        return tokenResponse("admin-token");
      }),
      http.get(`${apiBaseUrl}/auth/me`, ({ request }) => {
        if (request.headers.get("Authorization") === "Bearer admin-token") {
          return authMeResponse(adminUser);
        }
        return unauthenticatedResponse();
      }),
    );

    renderAt("/login");

    await userEvent.click(
      await screen.findByRole("button", { name: "Войти как администратор" }),
    );

    expect(await screen.findByRole("heading", { name: "Операторы" })).toBeVisible();
    expect(loginPayload).toEqual({
      username: "e2e-admin",
      password: "change-me-e2e-admin-password",
    });
    expect(window.location.pathname).toBe("/admin/operators");
  });

  it("logs in with the e2e operator shortcut", async () => {
    let loginPayload: Record<string, unknown> | null = null;
    server.use(
      http.post(`${apiBaseUrl}/auth/login`, async ({ request }) => {
        loginPayload = await readJsonObject(request);
        return tokenResponse("operator-token");
      }),
      http.get(`${apiBaseUrl}/auth/me`, ({ request }) => {
        if (request.headers.get("Authorization") === "Bearer operator-token") {
          return authMeResponse(operatorUser);
        }
        return unauthenticatedResponse();
      }),
    );

    renderAt("/login");

    await userEvent.click(await screen.findByRole("button", { name: "Войти как оператор" }));

    expect(await screen.findByRole("heading", { name: "Тренажёры" })).toBeVisible();
    expect(loginPayload).toEqual({
      username: "e2e-operator",
      password: "change-me-e2e-operator-password",
    });
    expect(window.location.pathname).toBe("/operator/simulators");
  });

  it("shows generic invalid login message", async () => {
    renderAt("/login");

    await userEvent.type(await screen.findByLabelText("Имя пользователя"), "missing");
    await userEvent.type(screen.getByLabelText("Пароль"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(
      await screen.findByText("Неверное имя пользователя или пароль"),
    ).toBeVisible();
  });

  it("bootstraps through refresh cookie and opens protected operator route", async () => {
    server.use(
      http.post(`${apiBaseUrl}/auth/refresh`, () => tokenResponse("operator-token")),
      http.get(`${apiBaseUrl}/auth/me`, ({ request }) => {
        if (request.headers.get("Authorization") === "Bearer operator-token") {
          return authMeResponse(operatorUser);
        }
        return unauthenticatedResponse();
      }),
    );

    renderAt("/operator/simulators");

    expect(await screen.findByRole("heading", { name: "Тренажёры" })).toBeVisible();
    expect(screen.getByText(/Оператор · оператор/u)).toBeVisible();
  });

  it("redirects operator after login to simulators", async () => {
    server.use(
      http.post(`${apiBaseUrl}/auth/login`, () => tokenResponse("operator-token")),
      http.get(`${apiBaseUrl}/auth/me`, ({ request }) => {
        if (request.headers.get("Authorization") === "Bearer operator-token") {
          return authMeResponse(operatorUser);
        }
        return unauthenticatedResponse();
      }),
    );

    renderAt("/login");

    await userEvent.type(await screen.findByLabelText("Имя пользователя"), "operator");
    await userEvent.type(screen.getByLabelText("Пароль"), "secret-password");
    await userEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("heading", { name: "Тренажёры" })).toBeVisible();
    expect(window.location.pathname).toBe("/operator/simulators");
  });

  it("redirects to login when refresh fails", async () => {
    renderAt("/operator/simulators");

    expect(await screen.findByRole("heading", { name: "Вход" })).toBeVisible();
    expect(window.location.pathname).toBe("/login");
  });

  it("shows forbidden view for an operator on admin route", async () => {
    setAccessToken("operator-token");
    server.use(
      http.get(`${apiBaseUrl}/auth/me`, ({ request }) => {
        if (request.headers.get("Authorization") === "Bearer operator-token") {
          return authMeResponse(operatorUser);
        }
        return unauthenticatedResponse();
      }),
    );

    renderAt("/admin/operators");

    await waitFor(() => {
      expect(screen.getByText("Этот раздел недоступен для вашей роли.")).toBeVisible();
    });
    expect(screen.getByText("Недостаточно прав")).toBeVisible();
  });
});

describe("admin operators", () => {
  it("creates operator and shows generated password once", async () => {
    useAdminSession();
    let createdOperator: User | null = null;
    server.use(
      http.get(`${apiBaseUrl}/operators`, () =>
        HttpResponse.json(operatorListResponse(createdOperator === null ? [] : [createdOperator])),
      ),
      http.get(`${apiBaseUrl}/operators/:operatorId/login-stats`, () =>
        HttpResponse.json(loginStatsResponse(0, null)),
      ),
      http.post(`${apiBaseUrl}/operators`, async ({ request }) => {
        const payload = await readJsonObject(request);
        createdOperator = {
          id: "4de8a566-4cf6-4ac7-b7ca-d0f4f2ba6ff1",
          username: readStringField(payload, "username"),
          full_name: readStringField(payload, "full_name"),
          role: "operator",
          is_active: true,
        };
        return HttpResponse.json(
          {
            operator: createdOperator,
            temporary_password: "generated-password-123",
          },
          { status: 201 },
        );
      }),
    );

    renderAt("/admin/operators");

    await userEvent.click(await screen.findByRole("button", { name: "Создать оператора" }));
    await userEvent.type(screen.getByLabelText("Имя пользователя"), "new-operator");
    await userEvent.type(screen.getByLabelText("ФИО"), "Новый Оператор");
    await userEvent.click(screen.getByRole("button", { name: "Создать" }));

    expect(await screen.findByText("generated-password-123")).toBeVisible();
    expect(screen.getByText(/Пароль показывается только один раз/u)).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(screen.queryByText("generated-password-123")).not.toBeInTheDocument();
  });

  it("shows conflict error on duplicate username", async () => {
    useAdminSession();
    server.use(
      http.get(`${apiBaseUrl}/operators`, () => HttpResponse.json(operatorListResponse([]))),
      http.post(`${apiBaseUrl}/operators`, () =>
        apiError(409, "USERNAME_ALREADY_EXISTS", "Пользователь с таким именем уже существует"),
      ),
    );

    renderAt("/admin/operators");

    await userEvent.click(await screen.findByRole("button", { name: "Создать оператора" }));
    await userEvent.type(screen.getByLabelText("Имя пользователя"), "duplicate");
    await userEvent.type(screen.getByLabelText("ФИО"), "Duplicate Operator");
    await userEvent.click(screen.getByRole("button", { name: "Создать" }));

    expect(
      await screen.findByText("Пользователь с таким именем уже существует"),
    ).toBeVisible();
  });

  it("deactivates operator after confirmation", async () => {
    useAdminSession();
    let operator: User = {
      id: "4de8a566-4cf6-4ac7-b7ca-d0f4f2ba6ff1",
      username: "operator-one",
      full_name: "Первый Оператор",
      role: "operator",
      is_active: true,
    };
    server.use(
      http.get(`${apiBaseUrl}/operators/:operatorId`, () => HttpResponse.json(operator)),
      http.get(`${apiBaseUrl}/operators/:operatorId/login-stats`, () =>
        HttpResponse.json(loginStatsResponse(3, "2026-07-13T05:00:00Z")),
      ),
      http.get(`${apiBaseUrl}/operators/:operatorId/login-history`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 } satisfies LoginHistoryResponse),
      ),
      http.patch(`${apiBaseUrl}/operators/:operatorId`, async ({ request }) => {
        const payload = await readJsonObject(request);
        operator = { ...operator, is_active: payload.is_active === true };
        return HttpResponse.json(operator);
      }),
    );

    renderAt(`/admin/operators/${operator.id}`);

    expect(await screen.findByRole("heading", { name: "Первый Оператор" })).toBeVisible();
    await userEvent.click(screen.getByRole("checkbox", { name: "Изменить активность оператора" }));
    await userEvent.click(screen.getByRole("button", { name: "Отключить" }));

    expect(await screen.findByText("Отключён")).toBeVisible();
  });

  it("resets password and shows login history", async () => {
    useAdminSession();
    const operator: User = {
      id: "4de8a566-4cf6-4ac7-b7ca-d0f4f2ba6ff1",
      username: "history-operator",
      full_name: "Оператор Истории",
      role: "operator",
      is_active: true,
    };
    server.use(
      http.get(`${apiBaseUrl}/operators/:operatorId`, () => HttpResponse.json(operator)),
      http.get(`${apiBaseUrl}/operators/:operatorId/login-stats`, () =>
        HttpResponse.json(loginStatsResponse(7, "2026-07-13T05:00:00Z")),
      ),
      http.get(`${apiBaseUrl}/operators/:operatorId/login-history`, () =>
        HttpResponse.json({
          items: [
            {
              id: "ef223f62-8370-489e-8ba1-50c80c483e55",
              occurred_at: "2026-07-13T05:00:00Z",
              success: true,
              failure_reason: null,
              ip_address: "127.0.0.1",
              user_agent: "MSW",
            },
          ],
          total: 1,
          limit: 10,
          offset: 0,
        } satisfies LoginHistoryResponse),
      ),
      http.post(`${apiBaseUrl}/operators/:operatorId/reset-password`, () =>
        HttpResponse.json({
          operator,
          temporary_password: "reset-password-123",
        }),
      ),
    );

    renderAt(`/admin/operators/${operator.id}`);

    expect(await screen.findByText("7")).toBeVisible();
    expect(screen.getByText("Успешно")).toBeVisible();
    expect(screen.getByText("127.0.0.1")).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Сбросить пароль" }));

    expect(await screen.findByText("reset-password-123")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(screen.queryByText("reset-password-123")).not.toBeInTheDocument();
  });
});

describe("operator simulator flow", () => {
  const simulator = {
    id: "0edfd69d-1353-40aa-a818-037952a46534",
    code: "boiler-demo",
    external_id: "boiler-001",
    name: "Котёл с двумя насосами",
    description: "Котёл, насос подачи пара и насос откачки пара.",
    visualization_type: "boiler-v1",
    is_active: true,
  };

  it("shows active simulator catalog card and hides admin flow from operator", async () => {
    useOperatorSession();
    server.use(http.get(`${apiBaseUrl}/simulators`, () => HttpResponse.json({ items: [simulator] })));

    renderAt("/operator/simulators");

    expect(await screen.findByRole("heading", { name: "Тренажёры" })).toBeVisible();
    expect(screen.getByText("Котёл с двумя насосами")).toBeVisible();
    expect(screen.getByText("Доступен")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Операторы" })).not.toBeInTheDocument();
  });

  it("blocks admin from operator flow", async () => {
    useAdminSession();

    renderAt("/operator/simulators");

    expect(await screen.findByText("Этот раздел недоступен для вашей роли.")).toBeVisible();
  });

  it("starts training once and redirects to session route", async () => {
    useOperatorSession();
    let createCount = 0;
    server.use(
      http.get(`${apiBaseUrl}/simulators/:simulatorId`, () => HttpResponse.json(simulator)),
      http.post(`${apiBaseUrl}/simulation-sessions`, () => {
        createCount += 1;
        return HttpResponse.json(
          {
            id: "37e020cf-0e03-4654-bef5-09b020210b22",
            operator_id: operatorUser.id,
            simulator_definition_id: simulator.id,
            external_session_id: "external-session-1",
            status: "active",
            started_at: "2026-07-13T05:00:00Z",
            ended_at: null,
            last_state: null,
            error_code: null,
            error_message: null,
            created_at: "2026-07-13T05:00:00Z",
            updated_at: "2026-07-13T05:00:00Z",
          },
          { status: 201 },
        );
      }),
      http.get(`${apiBaseUrl}/simulation-sessions/:sessionId`, () =>
        HttpResponse.json(sessionResponse()),
      ),
      http.get(`${apiBaseUrl}/simulation-sessions/:sessionId/state`, () =>
        HttpResponse.json({ state: boilerState(1) }),
      ),
    );

    renderAt(`/operator/simulators/${simulator.id}`);

    const startButton = await screen.findByRole("button", { name: "Начать тренировку" });
    await userEvent.dblClick(startButton);

    expect(await screen.findByRole("heading", { name: "Сессия тренировки" })).toBeVisible();
    expect(window.location.pathname).toBe("/operator/sessions/37e020cf-0e03-4654-bef5-09b020210b22");
    expect(createCount).toBe(1);
  });

  it("shows unavailable timeout and protocol errors", async () => {
    useOperatorSession();
    server.use(
      http.get(`${apiBaseUrl}/simulators`, () =>
        apiError(503, "SIMULATION_SERVICE_UNAVAILABLE", "Сервис моделирования недоступен"),
      ),
    );

    renderAt("/operator/simulators");

    expect(await screen.findByText("Сервис моделирования сейчас недоступен.")).toBeVisible();

    cleanup();
    server.use(
      http.get(`${apiBaseUrl}/simulators/:simulatorId`, () => HttpResponse.json(simulator)),
      http.post(`${apiBaseUrl}/simulation-sessions`, () =>
        apiError(504, "SIMULATION_TIMEOUT", "Сервис моделирования не ответил"),
      ),
    );
    renderAt(`/operator/simulators/${simulator.id}`);

    await userEvent.click(await screen.findByRole("button", { name: "Начать тренировку" }));
    expect(
      await screen.findByText("Сервис моделирования не ответил вовремя. Повторите попытку позже."),
    ).toBeVisible();

    cleanup();
    server.use(
      http.post(`${apiBaseUrl}/simulation-sessions`, () =>
        apiError(502, "SIMULATION_PROTOCOL_ERROR", "Ошибка сервиса моделирования"),
      ),
    );
    renderAt(`/operator/simulators/${simulator.id}`);

    await userEvent.click(await screen.findByRole("button", { name: "Начать тренировку" }));
    expect(await screen.findByText("Сервис моделирования вернул некорректный ответ.")).toBeVisible();
  });

  it("restores session metadata on session route refresh", async () => {
    useOperatorSession();
    installMockWebSocket();
    useSessionHandlers(boilerState(1));

    renderAt("/operator/sessions/37e020cf-0e03-4654-bef5-09b020210b22");

    expect(await screen.findByRole("heading", { name: "Сессия тренировки" })).toBeVisible();
    expect(screen.getByText(/external-session-1/u)).toBeVisible();
    expect(screen.getByText("Активна")).toBeVisible();
  });

  it("shows initial snapshot and applies newer authoritative state", async () => {
    useOperatorSession();
    installMockWebSocket();
    useSessionHandlers(boilerState(1));

    renderAt("/operator/sessions/37e020cf-0e03-4654-bef5-09b020210b22");

    expect(await screen.findByText("Revision: 1")).toBeVisible();
    MockWebSocket.instances[0]?.emit({ type: "state.snapshot", data: boilerState(2, "running") });
    expect(await screen.findByText("Revision: 2")).toBeVisible();
    expect(screen.getByText("Статус: running")).toBeVisible();
  });

  it("keeps accepted command pending until state event and blocks duplicate", async () => {
    useOperatorSession();
    installMockWebSocket();
    useSessionHandlers(boilerState(1));
    let commandCount = 0;
    server.use(
      http.post(`${apiBaseUrl}/simulation-sessions/:sessionId/commands`, () => {
        commandCount += 1;
        return HttpResponse.json({
          id: "cmd-row",
          session_id: "37e020cf-0e03-4654-bef5-09b020210b22",
          command_id: "client-command",
          equipment_id: "steam_supply_pump",
          action: "start",
          payload: {},
          status: "accepted",
          external_error_code: null,
          external_error_message: null,
          created_at: "2026-07-13T05:00:00Z",
          completed_at: "2026-07-13T05:00:00Z",
        });
      }),
    );

    renderAt("/operator/sessions/37e020cf-0e03-4654-bef5-09b020210b22");

    const startButton = (await screen.findAllByRole("button", { name: "Start" }))[0];
    await userEvent.dblClick(startButton);

    expect(await screen.findByText("Ожидает")).toBeVisible();
    expect(commandCount).toBe(1);

    MockWebSocket.instances[0]?.emit({ type: "state.snapshot", data: boilerState(2, "running") });
    expect(await screen.findByText("Принята")).toBeVisible();
  });

  it("shows rejected timeout malformed unknown events alarm revision and stop", async () => {
    useOperatorSession();
    installMockWebSocket();
    useSessionHandlers(boilerState(3));
    server.use(
      http.post(`${apiBaseUrl}/simulation-sessions/:sessionId/commands`, () =>
        HttpResponse.json({
          id: "cmd-row",
          session_id: "37e020cf-0e03-4654-bef5-09b020210b22",
          command_id: "client-command",
          equipment_id: "steam_supply_pump",
          action: "stop",
          payload: {},
          status: "rejected",
          external_error_code: "COMMAND_REJECTED",
          external_error_message: "Команда отклонена",
          created_at: "2026-07-13T05:00:00Z",
          completed_at: "2026-07-13T05:00:00Z",
        }),
      ),
      http.post(`${apiBaseUrl}/simulation-sessions/:sessionId/stop`, () =>
        HttpResponse.json({ ...sessionResponse(), status: "completed" }),
      ),
    );

    renderAt("/operator/sessions/37e020cf-0e03-4654-bef5-09b020210b22");

    expect(await screen.findByText("Revision: 3")).toBeVisible();
    MockWebSocket.instances[0]?.emit({ type: "state.snapshot", data: boilerState(2, "running") });
    expect(screen.getByText("Revision: 3")).toBeVisible();
    MockWebSocket.instances[0]?.emit({
      type: "alarm.raised",
      data: { code: "A1", severity: "warning", message: "Предупреждение", active: true },
    });
    expect(await screen.findByText("Предупреждение")).toBeVisible();
    MockWebSocket.instances[0]?.emitRaw("{bad-json");
    MockWebSocket.instances[0]?.emit({ type: "unknown.event", data: {} });
    expect(await screen.findByText("Получено некорректное событие WebSocket")).toBeVisible();
    expect(await screen.findByText("Получено неизвестное событие WebSocket")).toBeVisible();

    await userEvent.click(screen.getAllByRole("button", { name: "Stop" })[0]);
    expect(await screen.findByText("Отклонена")).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Завершить сессию" }));
    await waitFor(() => {
      expect(window.location.pathname).toBe("/operator/simulators");
    });
  });

  it("reconnects and requests snapshot after socket close", async () => {
    useOperatorSession();
    installMockWebSocket();
    let snapshotRevision = 1;
    server.use(
      http.get(`${apiBaseUrl}/simulation-sessions/:sessionId`, () => HttpResponse.json(sessionResponse())),
      http.get(`${apiBaseUrl}/simulation-sessions/:sessionId/state`, () =>
        HttpResponse.json({ state: boilerState(snapshotRevision) }),
      ),
    );

    renderAt("/operator/sessions/37e020cf-0e03-4654-bef5-09b020210b22");

    expect(await screen.findByText("Revision: 1")).toBeVisible();
    snapshotRevision = 4;
    MockWebSocket.instances[0]?.serverClose();

    expect(await screen.findByText("WebSocket переподключается")).toBeVisible();
    expect(await screen.findByText("Revision: 4")).toBeVisible();
  });

  it("supports keyboard command buttons", async () => {
    useOperatorSession();
    installMockWebSocket();
    useSessionHandlers(boilerState(1));
    server.use(
      http.post(`${apiBaseUrl}/simulation-sessions/:sessionId/commands`, () =>
        apiError(504, "SIMULATION_TIMEOUT", "Сервис моделирования не ответил"),
      ),
    );

    renderAt("/operator/sessions/37e020cf-0e03-4654-bef5-09b020210b22");

    const startButton = (await screen.findAllByRole("button", { name: "Start" }))[0];
    startButton.focus();
    await userEvent.keyboard("{Enter}");

    expect(await screen.findByText("Команда не выполнена: сервис моделирования не ответил.")).toBeVisible();
  });
});
