import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../src/entities/simulation/model/queries", () => ({
  useSimulationSessionQuery: () => ({
    isLoading: false,
    isError: false,
    data: {
      id: "session-1",
      operator_id: "operator-1",
      simulator_definition_id: "simulator-1",
      training_scenario_id: "scenario-1",
      mode: "training",
      external_session_id: "external-1",
      status: "completed",
      started_at: "2026-08-17T00:00:00Z",
      ended_at: "2026-08-17T00:01:00Z",
      last_state: null,
      error_code: null,
      error_message: null,
      created_at: "2026-08-17T00:00:00Z",
      updated_at: "2026-08-17T00:01:00Z",
    },
    refetch: vi.fn(),
  }),
}));

vi.mock("../src/entities/training/model/queries", () => ({
  useTrainingAssessmentQuery: () => ({
    isLoading: false,
    isError: false,
    data: {
      result: {
        id: "result-1",
        session_id: "session-1",
        scenario_id: "scenario-1",
        score: 85,
        max_score: 100,
        reaction_time_ms: 4200,
        error_count: 1,
        critical_error_count: 0,
        sequence_score: 100,
        reaction_score: 80,
        safety_score: 100,
        status: "final",
        summary: {},
        created_at: "2026-08-17T00:01:00Z",
        updated_at: "2026-08-17T00:01:00Z",
      },
      errors: [
        {
          id: "error-1",
          session_id: "session-1",
          scenario_expected_action_id: "step-1",
          error_type: "LATE_ACTION",
          severity: "warning",
          occurred_at_ms: 20_000,
          evidence: { delay_ms: 4200, allowed_delay_ms: 3000 },
          causal_chain: [{ kind: "classification" }],
          source: "rule",
          created_at: "2026-08-17T00:00:20Z",
        },
      ],
    },
    refetch: vi.fn(),
  }),
  useSessionTimelineQuery: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        id: "risk-1",
        session_id: "session-1",
        event_type: "ai.risk.updated",
        source: "ai",
        revision: 2,
        simulation_time_ms: 15_000,
        payload: {
          risk: 0.82,
          predicted_error_code: "ERROR_IN_NEXT_10_SECONDS",
          horizon_seconds: 10,
        },
        created_at: "2026-08-17T00:00:15Z",
      },
    ],
    refetch: vi.fn(),
  }),
  useSessionDebriefQuery: () => ({
    isLoading: false,
    isError: false,
    data: {
      session_id: "session-1",
      status: "final",
      generated_by: "rules",
      headline: "Результат 85/100; ошибок: 1.",
      strengths: ["Последовательность действий выполнена уверенно."],
      issues: ["LATE_ACTION"],
      recommendations: ["Повторить тренировку с контролем времени реакции."],
      recommended_scenario_code: "oil-heating-reaction-time-training",
      error_explanations: [],
    },
    refetch: vi.fn(),
  }),
}));

import { OperatorSessionResultPage } from "../src/pages/operator-session-result/OperatorSessionResultPage";

describe("OperatorSessionResultPage", () => {
  it("shows factual error, earlier ML prediction and actionable scenario recommendation", () => {
    render(
      <MemoryRouter initialEntries={["/operator/sessions/session-1/result"]}>
        <Routes>
          <Route
            path="/operator/sessions/:sessionId/result"
            element={<OperatorSessionResultPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Итоговый разбор сессии" })).toBeInTheDocument();
    expect(screen.getByText("85 / 100")).toBeInTheDocument();
    expect(screen.getByText("1 из 1")).toBeInTheDocument();
    expect(screen.getByText("ML риск")).toBeInTheDocument();
    expect(screen.getByText("Ошибка")).toBeInTheDocument();
    expect(screen.getByText("Поздняя реакция")).toBeInTheDocument();
    expect(
      screen.getByText("Повторить тренировку с контролем времени реакции."),
    ).toBeInTheDocument();
    expect(screen.getByText("oil-heating-reaction-time-training")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Перейти к рекомендованной тренировке" }),
    ).toHaveAttribute(
      "href",
      "/operator/simulators/simulator-1?scenario=oil-heating-reaction-time-training",
    );
  });
});
