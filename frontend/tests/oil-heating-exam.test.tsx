import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/widgets/oil-heating-simulator/model/useOilHeatingRuntime", () => ({
  useOilHeatingRuntime: () => ({
    state: null,
    connectionStatus: "connected",
    errors: [],
    sendPumpCommand: async () => undefined,
    sendValveCommand: async () => undefined,
    sendRegulatorCommand: async () => undefined,
    sendDosingCommand: async () => undefined,
    sendElouPumpCommand: async () => undefined,
    sendElouValveCommand: async () => undefined,
    sendElouRegulatorCommand: async () => undefined,
    sendElouDosingCommand: async () => undefined,
    sendElouVoltageCommand: async () => undefined,
    sendResetCommand: async () => undefined,
    isCommandPending: () => false,
    isValveCommandPending: () => false,
    isRegulatorCommandPending: () => false,
    isDosingCommandPending: () => false,
    isElouPumpCommandPending: () => false,
    isElouValveCommandPending: () => false,
    isElouRegulatorCommandPending: () => false,
    isElouDosingCommandPending: () => false,
    isElouVoltageCommandPending: () => false,
    isResetCommandPending: () => false,
  }),
}));

vi.mock("../src/widgets/oil-heating-simulator/OilHeatingScheme", () => ({
  OilHeatingScheme: () => <div>Oil heating scheme</div>,
}));

vi.mock("../src/widgets/ai-coach/AiCoachPanel", () => ({
  AiCoachPanel: () => <div>AI Coach Stub</div>,
}));

import type {
  SimulationSession,
  SimulationState,
} from "../src/entities/simulation/api/types";
import { OilHeatingSimulator } from "../src/widgets/oil-heating-simulator/OilHeatingSimulator";

const initialState: SimulationState = {
  revision: 1,
  simulation_time_ms: 0,
  boiler: { temperature_c: 0, pressure_bar: 0, status: "idle" },
  equipment: {},
  alarms: [],
};

function session(mode: "training" | "exam"): SimulationSession {
  return {
    id: `session-${mode}`,
    operator_id: "operator-1",
    simulator_definition_id: "simulator-1",
    training_scenario_id: "scenario-1",
    mode,
    external_session_id: "external-1",
    status: "active",
    started_at: "2026-08-17T00:00:00Z",
    ended_at: null,
    last_state: null,
    error_code: null,
    error_message: null,
    created_at: "2026-08-17T00:00:00Z",
    updated_at: "2026-08-17T00:00:00Z",
  };
}

afterEach(() => cleanup());

describe("OilHeatingSimulator AI visibility", () => {
  it("hides the AI coach during an active exam", () => {
    render(
      <OilHeatingSimulator
        session={session("exam")}
        initialState={initialState}
        stopping={false}
        onStop={() => undefined}
      />,
    );

    expect(screen.queryByText("AI Coach Stub")).not.toBeInTheDocument();
    expect(screen.getByText(/Экзаменационный режим/u)).toBeInTheDocument();
  });

  it("shows the AI coach during training", () => {
    render(
      <OilHeatingSimulator
        session={session("training")}
        initialState={initialState}
        stopping={false}
        onStop={() => undefined}
      />,
    );

    expect(screen.getByText("AI Coach Stub")).toBeInTheDocument();
  });
});
