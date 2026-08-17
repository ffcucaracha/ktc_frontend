import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  OperatorError,
  OperatorSkillProfile as SkillProfile,
  SimulationTimelineEvent,
} from "../src/entities/training/api/types";
import { OperatorSkillProfile } from "../src/widgets/operator-skill-profile/OperatorSkillProfile";
import { TrainingTimeline } from "../src/widgets/training-timeline/TrainingTimeline";


describe("training analytics components", () => {
  it("renders operator skill profile values", () => {
    const profile: SkillProfile = {
      operator_id: "operator-1",
      assessed_sessions: 3,
      average_score: 81,
      average_sequence_score: 92,
      average_reaction_score: 68,
      average_safety_score: 100,
      error_counts: { LATE_ACTION: 2 },
      weakest_skill: "reaction_speed",
      recent_scores: [85, 80, 78],
    };

    render(<OperatorSkillProfile profile={profile} />);

    expect(screen.getByText("Профиль навыков")).toBeInTheDocument();
    expect(screen.getByText("Последовательность операций")).toBeInTheDocument();
    expect(screen.getByText("Скорость реакции")).toBeInTheDocument();
    expect(screen.getByText("68 / 100")).toBeInTheDocument();
    expect(screen.getByText(/Слабая зона: Скорость реакции/u)).toBeInTheDocument();
  });

  it("visually distinguishes an ML prediction from the actual error", () => {
    const timeline: SimulationTimelineEvent[] = [
      {
        id: "risk-1",
        session_id: "session-1",
        event_type: "ai.risk.updated",
        source: "ai",
        revision: 1,
        simulation_time_ms: 15_000,
        payload: { risk: 0.82, predicted_error_code: "ERROR_IN_NEXT_10_SECONDS" },
        created_at: "2026-08-17T00:00:15Z",
      },
    ];
    const errors: OperatorError[] = [
      {
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
      },
    ];

    render(<TrainingTimeline timeline={timeline} errors={errors} />);

    expect(screen.getByText("ML риск")).toBeInTheDocument();
    expect(screen.getByText("Ошибка")).toBeInTheDocument();
    expect(screen.getByText(/82%/u)).toBeInTheDocument();
    expect(screen.getByText("Поздняя реакция")).toBeInTheDocument();
  });
});
