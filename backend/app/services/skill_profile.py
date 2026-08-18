from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperatorError, OperatorErrorType, TrainingResult
from app.repositories.assessment import AssessmentRepository
from app.repositories.operator_skill_profiles import OperatorSkillProfileRepository

MVP_SKILLS = (
    "pump_control",
    "regulation",
    "alarm_handling",
    "reaction_speed",
    "procedure_sequence",
    "emergency_response",
)


@dataclass(frozen=True)
class SkillSnapshot:
    skill_code: str
    score: float
    sample_count: int


class SkillProfileService:
    """Build an explainable, idempotent skill profile from final assessment facts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._assessment = AssessmentRepository(session)
        self._profiles = OperatorSkillProfileRepository(session)

    async def rebuild_operator(self, operator_id: UUID) -> list[SkillSnapshot]:
        results = [
            item
            for item in await self._assessment.list_results_for_operator(operator_id)
            if item.status == "final"
        ]
        errors = await self._assessment.list_errors_for_operator(operator_id)
        values = build_skill_values(results, errors)
        await self._profiles.replace_for_operator(operator_id, values)
        await self._session.commit()
        return [
            SkillSnapshot(skill_code=code, score=score, sample_count=count)
            for code, (score, count) in sorted(values.items())
        ]

    async def list_operator(self, operator_id: UUID) -> list[SkillSnapshot]:
        items = await self._profiles.list_for_operator(operator_id)
        return [
            SkillSnapshot(
                skill_code=item.skill_code,
                score=round(item.score, 1),
                sample_count=item.sample_count,
            )
            for item in items
        ]


def build_skill_values(
    results: list[TrainingResult],
    errors: list[OperatorError],
) -> dict[str, tuple[float, int]]:
    if not results:
        return {skill: (0.0, 0) for skill in MVP_SKILLS}

    by_session: dict[UUID, list[OperatorError]] = defaultdict(list)
    for error in errors:
        by_session[error.session_id].append(error)

    samples: dict[str, list[float]] = {skill: [] for skill in MVP_SKILLS}
    for result in results:
        session_errors = by_session.get(result.session_id, [])
        samples["procedure_sequence"].append(result.sequence_score)
        samples["reaction_speed"].append(result.reaction_score)
        samples["emergency_response"].append(result.safety_score)

        pump_penalty = 0.0
        regulation_penalty = 0.0
        alarm_signal = False
        for error in session_errors:
            equipment_id = _equipment_id(error)
            if equipment_id.startswith("H1") or equipment_id.startswith("steam_"):
                pump_penalty += _penalty(error.error_type)
            if equipment_id.startswith("FRC"):
                regulation_penalty += _penalty(error.error_type)
            if "alarm" in str(error.evidence).lower():
                alarm_signal = True

        samples["pump_control"].append(max(0.0, 100.0 - pump_penalty))
        samples["regulation"].append(max(0.0, 100.0 - regulation_penalty))
        if alarm_signal:
            samples["alarm_handling"].append(result.safety_score)

    values: dict[str, tuple[float, int]] = {}
    for skill in MVP_SKILLS:
        skill_samples = samples[skill]
        values[skill] = (
            round(sum(skill_samples) / len(skill_samples), 1) if skill_samples else 0.0,
            len(skill_samples),
        )
    return values


def _equipment_id(error: OperatorError) -> str:
    actual = error.evidence.get("actual")
    if isinstance(actual, dict):
        value = actual.get("equipment_id")
        if isinstance(value, str):
            return value
    value = error.evidence.get("equipment_id")
    return value if isinstance(value, str) else ""


def _penalty(error_type: OperatorErrorType | str) -> float:
    normalized = (
        error_type
        if isinstance(error_type, OperatorErrorType)
        else OperatorErrorType(str(error_type))
    )
    return {
        OperatorErrorType.WRONG_ACTION: 20.0,
        OperatorErrorType.WRONG_SEQUENCE: 15.0,
        OperatorErrorType.LATE_ACTION: 10.0,
        OperatorErrorType.MISSED_ACTION: 20.0,
    }[normalized]
