import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/entities/training/api/trainingApi", () => ({
  createTrainingEventSocket: vi.fn(),
}));

import { createTrainingEventSocket } from "../src/entities/training/api/trainingApi";
import { AiCoachPanel } from "../src/widgets/ai-coach/AiCoachPanel";

class FakeSocket {
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  close = vi.fn();
}

let socket: FakeSocket;

beforeEach(() => {
  socket = new FakeSocket();
  vi.mocked(createTrainingEventSocket).mockReturnValue(socket as unknown as WebSocket);
});

describe("AiCoachPanel", () => {
  it("renders a realtime risk prediction", () => {
    render(<AiCoachPanel sessionId="session-1" />);

    act(() => {
      socket.onopen?.(new Event("open"));
      socket.onmessage?.(
        new MessageEvent<string>("message", {
          data: JSON.stringify({
            type: "ai.risk.updated",
            data: {
              risk: 0.82,
              predicted_error_code: "LATE_ACTION",
              horizon_seconds: 10,
              model_version: "risk-catboost-v1",
              decision_threshold: 0.2,
              features: [{ name: "pressure_delta_10s", importance: 0.31 }],
            },
          }),
        }),
      );
    });

    expect(screen.getByText("подключён")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText("Прогноз: LATE_ACTION")).toBeInTheDocument();
    expect(screen.getByText(/Повышенный риск ошибки/u)).toBeInTheDocument();
    expect(screen.getByText(/изменение давления за 10 с/u)).toBeInTheDocument();
  });

  it("uses the model decision threshold instead of a hardcoded 50 percent", () => {
    render(<AiCoachPanel sessionId="session-threshold" />);

    act(() => {
      socket.onopen?.(new Event("open"));
      socket.onmessage?.(
        new MessageEvent<string>("message", {
          data: JSON.stringify({
            type: "ai.risk.updated",
            data: {
              risk: 0.23,
              predicted_error_code: "ERROR_IN_NEXT_10_SECONDS",
              horizon_seconds: 10,
              model_version: "risk-catboost-v2",
              decision_threshold: 0.2,
              features: [{ name: "time_since_last_action_s", importance: 0.15 }],
            },
          }),
        }),
      );
    });

    expect(screen.getByText("Повышенный риск ошибки: 23%")).toBeInTheDocument();
    expect(screen.getByText("Прогноз: ERROR_IN_NEXT_10_SECONDS")).toBeInTheDocument();
  });

  it("shows fail-open state when AI websocket is unavailable", () => {
    render(<AiCoachPanel sessionId="session-2" />);

    act(() => {
      socket.onerror?.(new Event("error"));
    });

    expect(screen.getByText("недоступен")).toBeInTheDocument();
    expect(
      screen.getByText(
        "AI временно недоступен. Управление установкой продолжает работать независимо от него.",
      ),
    ).toBeInTheDocument();
  });
});
