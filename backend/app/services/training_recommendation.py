from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TrainingScenario, TrainingScenarioDifficulty
from app.repositories.training_scenarios import TrainingScenarioRepository


@dataclass(frozen=True)
class RecommendedScenario:
    id: UUID
    code: str
    name: str
    simulator_definition_id: UUID


_FOCUS_TO_ASSESSMENT_TAGS: dict[str, tuple[str, ...]] = {
    "procedure_sequence": ("wrong_sequence", "sequence", "missed_action"),
    "reaction_speed": ("reaction_time", "late_action"),
    "regulation": ("setpoint",),
    "pump_control": ("sequence", "missed_action"),
}


class TrainingScenarioSelector:
    """Choose an active scenario from scenario metadata, never from LLM-generated text."""

    def __init__(self, session: AsyncSession) -> None:
        self._scenarios = TrainingScenarioRepository(session)

    async def select_for_focus(
        self,
        *,
        simulator_id: UUID,
        focus: str,
    ) -> RecommendedScenario | None:
        scenarios = await self._scenarios.list_active_for_simulator(simulator_id)
        if not scenarios:
            return None

        if focus == "baseline":
            candidates = [item for item in scenarios if item.difficulty == TrainingScenarioDifficulty.BASIC]
            selected = min(candidates or scenarios, key=_baseline_sort_key)
            return _map_scenario(selected)

        preferred_tags = _FOCUS_TO_ASSESSMENT_TAGS.get(focus)
        if preferred_tags is None:
            return None

        ranked: list[tuple[tuple[int, int, int, str], TrainingScenario]] = []
        for scenario in scenarios:
            assessment_focus = _assessment_focus(scenario)
            matching_ranks = [
                preferred_tags.index(tag)
                for tag in assessment_focus
                if tag in preferred_tags
            ]
            if not matching_ranks:
                continue
            ranked.append(
                (
                    (
                        min(matching_ranks),
                        len(assessment_focus),
                        _difficulty_rank(scenario.difficulty),
                        scenario.code,
                    ),
                    scenario,
                )
            )

        if not ranked:
            return None
        return _map_scenario(min(ranked, key=lambda item: item[0])[1])


def _assessment_focus(scenario: TrainingScenario) -> tuple[str, ...]:
    raw = scenario.config.get("assessment_focus")
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, str) and item.strip())


def _difficulty_rank(difficulty: TrainingScenarioDifficulty) -> int:
    return {
        TrainingScenarioDifficulty.BASIC: 0,
        TrainingScenarioDifficulty.MEDIUM: 1,
        TrainingScenarioDifficulty.ADVANCED: 2,
    }.get(difficulty, 99)


def _baseline_sort_key(scenario: TrainingScenario) -> tuple[int, str]:
    # Prefer the canonical startup scenario as a neutral first assessment when available.
    return (0 if "startup" in scenario.code else 1, scenario.code)


def _map_scenario(scenario: TrainingScenario) -> RecommendedScenario:
    return RecommendedScenario(
        id=scenario.id,
        code=scenario.code,
        name=scenario.name,
        simulator_definition_id=scenario.simulator_definition_id,
    )
