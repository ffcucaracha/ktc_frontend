import { describe, expect, it } from "vitest";

import type { TrainingResult } from "../src/entities/training/api/types";
import { aggregateOperatorTrainingStats } from "../src/entities/training/lib/admin";

function result(overrides: Partial<TrainingResult>): TrainingResult {
  return {
    id: crypto.randomUUID(),
    session_id: crypto.randomUUID(),
    scenario_id: crypto.randomUUID(),
    score: 80,
    max_score: 100,
    reaction_time_ms: 4000,
    error_count: 1,
    critical_error_count: 0,
    sequence_score: 80,
    reaction_score: 80,
    safety_score: 100,
    status: "final",
    summary: {},
    created_at: "2026-08-17T00:00:00Z",
    updated_at: "2026-08-17T00:00:00Z",
    ...overrides,
  };
}

describe("aggregateOperatorTrainingStats", () => {
  it("aggregates scores, reaction time and critical errors", () => {
    const stats = aggregateOperatorTrainingStats([
      result({ score: 80, reaction_time_ms: 4000, critical_error_count: 1 }),
      result({ score: 100, reaction_time_ms: 2000, critical_error_count: 2 }),
    ]);

    expect(stats.sessions).toBe(2);
    expect(stats.averageScore).toBe(90);
    expect(stats.averageReactionTimeMs).toBe(3000);
    expect(stats.criticalErrors).toBe(3);
  });

  it("ignores null reaction times", () => {
    const stats = aggregateOperatorTrainingStats([
      result({ reaction_time_ms: null }),
      result({ reaction_time_ms: 2500 }),
    ]);

    expect(stats.averageReactionTimeMs).toBe(2500);
  });
});
