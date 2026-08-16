import { describe, expect, it } from "vitest";

import type { OperatorError, SimulationTimelineEvent } from "../src/entities/training/api/types";
import { buildResultTimelineItems, formatDurationMs } from "../src/entities/training/lib/result";

function event(overrides: Partial<SimulationTimelineEvent>): SimulationTimelineEvent {
  return {
    id: "event-1",
    session_id: "session-1",
    event_type: "state.snapshot",
    source: "system",
    revision: 1,
    simulation_time_ms: 0,
    payload: {},
    created_at: "2026-08-17T00:00:00Z",
    ...overrides,
  };
}

function operatorError(overrides: Partial<OperatorError>): OperatorError {
  return {
    id: "error-1",
    session_id: "session-1",
    scenario_expected_action_id: null,
    error_type: "LATE_ACTION",
    severity: "warning",
    occurred_at_ms: 20_000,
    evidence: {},
    causal_chain: [],
    source: "rule",
    created_at: "2026-08-17T00:00:20Z",
    ...overrides,
  };
}

describe("training result formatting", () => {
  it("places a prior ML risk prediction before the factual error", () => {
    const items = buildResultTimelineItems(
      [
        event({
          id: "risk-1",
          event_type: "ai.risk.updated",
          simulation_time_ms: 15_000,
          payload: { risk: 0.82, predicted_error_code: "ERROR_IN_NEXT_10_SECONDS" },
          created_at: "2026-08-17T00:00:15Z",
        }),
      ],
      [operatorError({ occurred_at_ms: 20_000 })],
    );

    expect(items.map((item) => item.kind)).toEqual(["risk", "error"]);
    expect(items[0]?.title).toContain("82%");
  });

  it("samples dense snapshots instead of flooding the result timeline", () => {
    const items = buildResultTimelineItems(
      [
        event({ id: "snapshot-1", simulation_time_ms: 0 }),
        event({ id: "snapshot-2", simulation_time_ms: 2_000, revision: 2 }),
        event({ id: "snapshot-3", simulation_time_ms: 10_000, revision: 3 }),
      ],
      [],
    );

    expect(items.filter((item) => item.kind === "state")).toHaveLength(2);
  });

  it("formats reaction time for the summary", () => {
    expect(formatDurationMs(2500)).toBe("2.50 с");
  });
});
