from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperatorError, OperatorErrorType, TrainingResult
from app.repositories.assessment import AssessmentRepository
from app.services.skill_profile import SkillProfileService


@dataclass(frozen=True)
class SkillProfile:
    operator_id: UUID
    assessed_sessions: int
    average_score: float | None
    average_sequence_score: float | None
    average_reaction_score: float | None
    average_safety_score: float | None
    error_counts: dict[str, int]
    weakest_skill: str | None
    recent_scores: list[float]


@dataclass(frozen=True)
class TrainingRecommendation:
    focus: str
    priority: int
    reason: str


class TrainingInsightsService:
    def __init__(self, session: AsyncSession) -> None:
        self._assessment = AssessmentRepository(session)
        self._skills = SkillProfileService(session)

    async def list_results(self, operator_id: UUID) -> list[TrainingResult]:
        return await self._assessment.list_results_for_operator(operator_id)

    async def build_skill_profile(self, operator_id: UUID) -> SkillProfile:
        results = await self._assessment.list_results_for_operator(operator_id)
        errors = await self._assessment.list_errors_for_operator(operator_id)
        persisted = await self._skills.rebuild_operator(operator_id)
        profile = build_skill_profile(operator_id, results, errors)
        observed = [item for item in persisted if item.sample_count > 0]
        weakest = min(observed, key=lambda item: item.score).skill_code if observed else None
        return SkillProfile(
            operator_id=profile.operator_id,
            assessed_sessions=profile.assessed_sessions,
            average_score=profile.average_score,
            average_sequence_score=profile.average_sequence_score,
            average_reaction_score=profile.average_reaction_score,
            average_safety_score=profile.average_safety_score,
            error_counts=profile.error_counts,
            weakest_skill=weakest,
            recent_scores=profile.recent_scores,
        )

    async def build_recommendations(
        self,
        operator_id: UUID,
    ) -> list[TrainingRecommendation]:
        profile = await self.build_skill_profile(operator_id)
        return build_recommendations(profile)


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def build_skill_profile(
    operator_id: UUID,
    results: list[TrainingResult],
    errors: list[OperatorError],
) -> SkillProfile:
    final_results = [item for item in results if item.status == "final"]
    error_counter = Counter(item.error_type.value for item in errors)
    skill_averages = {
        "sequence": _average([item.sequence_score for item in final_results]),
        "reaction": _average([item.reaction_score for item in final_results]),
        "safety": _average([item.safety_score for item in final_results]),
    }
    known_skills = {key: value for key, value in skill_averages.items() if value is not None}
    weakest_skill = min(known_skills, key=known_skills.get) if known_skills else None

    return SkillProfile(
        operator_id=operator_id,
        assessed_sessions=len(final_results),
        average_score=_average([item.score for item in final_results]),
        average_sequence_score=skill_averages["sequence"],
        average_reaction_score=skill_averages["reaction"],
        average_safety_score=skill_averages["safety"],
        error_counts=dict(sorted(error_counter.items())),
        weakest_skill=weakest_skill,
        recent_scores=[round(item.score, 1) for item in final_results[:5]],
    )


def build_recommendations(profile: SkillProfile) -> list[TrainingRecommendation]:
    if profile.assessed_sessions == 0:
        return [
            TrainingRecommendation(
                focus="baseline",
                priority=1,
                reason="Пройти базовый сценарий для формирования исходного профиля навыков.",
            )
        ]

    recommendations: list[TrainingRecommendation] = []
    error_counts = profile.error_counts

    wrong_sequence = error_counts.get(OperatorErrorType.WRONG_SEQUENCE.value, 0)
    late_action = error_counts.get(OperatorErrorType.LATE_ACTION.value, 0)
    missed_action = error_counts.get(OperatorErrorType.MISSED_ACTION.value, 0)
    wrong_action = error_counts.get(OperatorErrorType.WRONG_ACTION.value, 0)

    if wrong_sequence > 0:
        recommendations.append(
            TrainingRecommendation(
                focus="procedure_sequence",
                priority=1,
                reason=(
                    f"Зафиксировано {wrong_sequence} ошибок порядка действий; "
                    "рекомендуется повторить сценарий с контролем последовательности."
                ),
            )
        )
    if late_action > 0:
        recommendations.append(
            TrainingRecommendation(
                focus="reaction_speed",
                priority=2,
                reason=(
                    f"Зафиксировано {late_action} поздних действий; "
                    "рекомендуется повторить тренировку с ограниченным временем реакции."
                ),
            )
        )
    if missed_action > 0:
        recommendations.append(
            TrainingRecommendation(
                focus="procedure_sequence",
                priority=3,
                reason=(
                    f"Пропущено обязательных шагов: {missed_action}; "
                    "нужно отработать полное выполнение процедуры."
                ),
            )
        )
    if wrong_action > 0:
        recommendations.append(
            TrainingRecommendation(
                focus="pump_control",
                priority=4,
                reason=(
                    f"Зафиксировано {wrong_action} неверных команд или уставок; "
                    "рекомендуется повторить управление оборудованием и регуляторами."
                ),
            )
        )

    if not recommendations and profile.weakest_skill is not None:
        recommendations.append(
            TrainingRecommendation(
                focus=profile.weakest_skill,
                priority=1,
                reason=f"Закрепить наиболее слабый измеренный навык: {profile.weakest_skill}.",
            )
        )

    return sorted(recommendations, key=lambda item: item.priority)
