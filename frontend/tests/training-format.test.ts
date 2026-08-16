import { describe, expect, it } from "vitest";

import { buildCoachMessage, formatRiskPercent } from "../src/entities/training/lib/format";

describe("training risk formatting", () => {
  it("formats probability as a bounded percent", () => {
    expect(formatRiskPercent(0.846)).toBe("85%");
    expect(formatRiskPercent(2)).toBe("100%");
  });

  it("builds an explainable coach message from model output", () => {
    const message = buildCoachMessage(
      {
        risk: 0.81,
        predicted_error_code: "ERROR_IN_NEXT_10_SECONDS",
        horizon_seconds: 10,
        model_version: "risk-catboost-v1",
        features: [{ name: "pressure_delta_10s", importance: 0.31 }],
      },
      new Date("2026-08-16T12:00:00Z"),
    );

    expect(message.title).toContain("81%");
    expect(message.reason).toContain("изменение давления за 10 с");
    expect(message.recommendation).toContain("последовательностью сценария");
  });
});
