from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.integrations.ai.base import AIGateway
from app.integrations.ai.dto import (
    DebriefError,
    DebriefRequest,
    ErrorExplanation,
    ErrorExplanationRequest,
)
from app.integrations.ai.errors import AIIntegrationError
from app.models import OperatorError, TrainingResult

MAX_INLINE_ERROR_EXPLANATIONS = 3


@dataclass(frozen=True)
class ErrorNarrative:
    error_id: UUID
    summary: str
    explanation: str
    recommendation: str
    sources: list[dict[str, object]]
    model: str


@dataclass(frozen=True)
class SessionNarrative:
    generated_by: str
    debrief_model: str
    headline: str
    strengths: list[str]
    issues: list[str]
    recommendations: list[str]
    recommended_scenario_code: str | None
    error_explanations: list[ErrorNarrative]
    ai_error_code: str | None = None


class TrainingNarrativeService:
    """Ask AI-service to verbalize verified assessment facts, with deterministic fallback."""

    def __init__(self, gateway: AIGateway) -> None:
        self._gateway = gateway

    async def build(
        self,
        *,
        result: TrainingResult,
        errors: list[OperatorError],
        scenario_code: str | None,
        recommended_scenario_code: str | None = None,
    ) -> SessionNarrative:
        fallback = _fallback_session(
            result,
            errors,
            recommended_scenario_code=recommended_scenario_code,
        )
        scenario_metadata: dict[str, object] = {}
        if scenario_code is not None:
            scenario_metadata["scenario_code"] = scenario_code
        if recommended_scenario_code is not None:
            scenario_metadata["recommended_scenario_code"] = recommended_scenario_code

        try:
            debrief = await self._gateway.build_debrief(
                DebriefRequest(
                    session_id=result.session_id,
                    session_result={
                        "score": result.score,
                        "max_score": result.max_score,
                        "sequence_score": result.sequence_score,
                        "reaction_score": result.reaction_score,
                        "safety_score": result.safety_score,
                        "error_count": result.error_count,
                        "critical_error_count": result.critical_error_count,
                    },
                    errors=[
                        DebriefError(
                            error_code=item.error_type.value,
                            severity=item.severity,
                            evidence=item.evidence,
                        )
                        for item in errors
                    ],
                    reaction_metrics={"average_reaction_time_ms": result.reaction_time_ms},
                    scenario_metadata=scenario_metadata,
                )
            )
            explanations = [
                await self._explain(item) for item in errors[:MAX_INLINE_ERROR_EXPLANATIONS]
            ]
        except AIIntegrationError as exc:
            return _fallback_session(
                result,
                errors,
                recommended_scenario_code=recommended_scenario_code,
                ai_error_code=exc.code.value,
            )

        generated_by = "rules" if _is_fallback_model(debrief.model) else debrief.model
        return SessionNarrative(
            generated_by=generated_by,
            debrief_model=debrief.model,
            headline=debrief.short_summary,
            strengths=debrief.strengths or fallback.strengths,
            issues=debrief.weaknesses or fallback.issues,
            recommendations=debrief.priority_actions or fallback.recommendations,
            # Scenario selection belongs to deterministic personalization. LLM may verbalize it,
            # but cannot invent or override the scenario chosen from active backend scenarios.
            recommended_scenario_code=recommended_scenario_code,
            error_explanations=explanations,
        )

    async def _explain(self, error: OperatorError) -> ErrorNarrative:
        actual = error.evidence.get("actual")
        explanation = await self._gateway.explain_error(
            ErrorExplanationRequest(
                error_code=error.error_type.value,
                severity=error.severity,
                actual_action=actual if isinstance(actual, dict) else None,
                process_context={"evidence": error.evidence},
                cause=error.causal_chain,
                consequences=[],
                regulation_context=[],
            )
        )
        return _map_explanation(error.id, explanation)


def _map_explanation(error_id: UUID, explanation: ErrorExplanation) -> ErrorNarrative:
    return ErrorNarrative(
        error_id=error_id,
        summary=explanation.summary,
        explanation=explanation.explanation,
        recommendation=explanation.recommendation,
        sources=[dict(item) for item in explanation.sources],
        model=explanation.model,
    )


def _fallback_session(
    result: TrainingResult,
    errors: list[OperatorError],
    *,
    recommended_scenario_code: str | None = None,
    ai_error_code: str | None = None,
) -> SessionNarrative:
    issue_types = sorted({item.error_type.value for item in errors})
    strengths: list[str] = []
    if result.sequence_score >= 90:
        strengths.append("Последовательность действий выполнена уверенно.")
    if result.reaction_score >= 90:
        strengths.append("Время реакции соответствует требованиям сценария.")
    if result.safety_score >= 90:
        strengths.append("Критических нарушений безопасности не выявлено.")
    if not strengths:
        strengths.append("Сессия завершена и доступна для детального разбора.")

    mapping = {
        "WRONG_SEQUENCE": "Повторить сценарий с фокусом на порядок операций.",
        "LATE_ACTION": "Повторить тренировку с контролем времени реакции.",
        "MISSED_ACTION": "Отработать выполнение всех обязательных шагов сценария.",
        "WRONG_ACTION": "Повторить работу с командами оборудования и уставками.",
    }
    recommendations = [mapping[item] for item in issue_types if item in mapping]
    if not recommendations:
        recommendations.append("Закрепить результат повторным прохождением сценария.")

    return SessionNarrative(
        generated_by="rules",
        debrief_model="rules-fallback-v1",
        headline=(
            f"Результат {result.score:.0f}/{result.max_score:.0f}; ошибок: {result.error_count}."
        ),
        strengths=strengths,
        issues=issue_types,
        recommendations=recommendations,
        recommended_scenario_code=recommended_scenario_code,
        error_explanations=[],
        ai_error_code=ai_error_code,
    )


def _is_fallback_model(model: str) -> bool:
    return model.startswith("mock-") or model.startswith("rules-")
