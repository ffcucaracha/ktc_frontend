import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OperatorRecommendationCard } from "../src/widgets/operator-recommendation/OperatorRecommendationCard";


describe("OperatorRecommendationCard", () => {
  it("shows the highest-priority recommendation and selected scenario", () => {
    render(
      <OperatorRecommendationCard
        data={{
          operator_id: "operator-1",
          source: "rules",
          items: [
            {
              focus: "reaction_speed",
              priority: 2,
              reason: "Поздние действия.",
              scenario_id: "scenario-reaction",
              scenario_code: "oil-heating-reaction-time-training",
              scenario_name: "Тренировка времени реакции",
            },
            {
              focus: "procedure_sequence",
              priority: 1,
              reason: "Ошибки порядка действий.",
              scenario_id: "scenario-sequence",
              scenario_code: "oil-heating-wrong-sequence-training",
              scenario_name: "Контроль последовательности запуска",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("Фокус: procedure_sequence")).toBeInTheDocument();
    expect(screen.getByText("Контроль последовательности запуска")).toBeInTheDocument();
    expect(screen.queryByText("Тренировка времени реакции")).not.toBeInTheDocument();
  });
});
