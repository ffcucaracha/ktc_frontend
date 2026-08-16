from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin, require_operator
from app.api.errors import ApiError
from app.db.session import get_session
from app.models import SimulationSessionStatus, TrainingSessionMode, User, UserRole
from app.repositories.simulation_events import SimulationEventRepository
from app.repositories.simulation_sessions import SimulationSessionRepository
from app.repositories.users import UserRepository
from app.schemas.training import (
    DebriefResponse,
    OperatorErrorResponse,
    OperatorErrorsResponse,
    SimulationTimelineEventResponse,
    SimulationTimelineResponse,
    SkillProfileResponse,
    TrainingAssessmentResponse,
    TrainingRecommendationResponse,
    TrainingRecommendationsResponse,
    TrainingResultListResponse,
    TrainingResultResponse,
)
from app.services.assessment import (
    AssessmentScenarioRequiredError,
    AssessmentService,
    AssessmentSessionNotFoundError,
)
from app.services.training_insights import TrainingInsightsService

router = APIRouter(tags=["training"])


def _session_not_found() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", "Сессия не найдена")


def _scenario_required() -> ApiError:
    return ApiError(
        status.HTTP_409_CONFLICT,
        "TRAINING_SCENARIO_REQUIRED",
        "Для оценки сессия должна быть запущена с учебным сценарием",
    )


def _operator_not_found() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "OPERATOR_NOT_FOUND", "Оператор не найден")


def _exam_hints_unavailable() -> ApiError:
    return ApiError(
        status.HTTP_409_CONFLICT,
        "EXAM_HINTS_UNAVAILABLE",
        "Разбор экзамена доступен только после завершения сессии",
    )


async def _require_operator_target(session: AsyncSession, operator_id: UUID) -> User:
    user = await UserRepository(session).get_by_id(operator_id)
    if user is None or user.role != UserRole.OPERATOR:
        raise _operator_not_found()
    return user


@router.get(
    "/simulation-sessions/{session_id}/assessment",
    response_model=TrainingAssessmentResponse,
)
@router.post(
    "/simulation-sessions/{session_id}/assessment",
    response_model=TrainingAssessmentResponse,
)
async def get_session_assessment(
    session_id: UUID,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TrainingAssessmentResponse:
    try:
        outcome = await AssessmentService(session).assess_session(session_id, operator.id)
    except AssessmentSessionNotFoundError as exc:
        raise _session_not_found() from exc
    except AssessmentScenarioRequiredError as exc:
        raise _scenario_required() from exc

    return TrainingAssessmentResponse(
        result=TrainingResultResponse.model_validate(outcome.result),
        errors=[OperatorErrorResponse.model_validate(item) for item in outcome.errors],
    )


@router.get(
    "/simulation-sessions/{session_id}/errors",
    response_model=OperatorErrorsResponse,
)
async def get_session_errors(
    session_id: UUID,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperatorErrorsResponse:
    try:
        outcome = await AssessmentService(session).assess_session(session_id, operator.id)
    except AssessmentSessionNotFoundError as exc:
        raise _session_not_found() from exc
    except AssessmentScenarioRequiredError as exc:
        raise _scenario_required() from exc
    return OperatorErrorsResponse(
        items=[OperatorErrorResponse.model_validate(item) for item in outcome.errors]
    )


@router.get(
    "/simulation-sessions/{session_id}/timeline",
    response_model=SimulationTimelineResponse,
)
async def get_session_timeline(
    session_id: UUID,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SimulationTimelineResponse:
    simulation_session = await SimulationSessionRepository(session).get_for_operator(
        session_id,
        operator.id,
    )
    if simulation_session is None:
        raise _session_not_found()
    events = await SimulationEventRepository(session).list_for_session(session_id)
    return SimulationTimelineResponse(
        items=[SimulationTimelineEventResponse.model_validate(item) for item in events]
    )


@router.get(
    "/simulation-sessions/{session_id}/debrief",
    response_model=DebriefResponse,
)
async def get_session_debrief(
    session_id: UUID,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DebriefResponse:
    simulation_session = await SimulationSessionRepository(session).get_for_operator(
        session_id,
        operator.id,
    )
    if simulation_session is None:
        raise _session_not_found()
    if (
        simulation_session.mode == TrainingSessionMode.EXAM
        and simulation_session.status == SimulationSessionStatus.ACTIVE
    ):
        raise _exam_hints_unavailable()

    try:
        outcome = await AssessmentService(session).assess_session(session_id, operator.id)
    except AssessmentScenarioRequiredError as exc:
        raise _scenario_required() from exc

    errors = outcome.errors
    issue_types = sorted({item.error_type.value for item in errors})
    strengths: list[str] = []
    if outcome.result.sequence_score >= 90:
        strengths.append("Последовательность действий выполнена уверенно.")
    if outcome.result.reaction_score >= 90:
        strengths.append("Время реакции соответствует требованиям сценария.")
    if outcome.result.safety_score >= 90:
        strengths.append("Критических нарушений безопасности не выявлено.")
    if not strengths:
        strengths.append("Сессия завершена и доступна для детального разбора.")

    recommendations: list[str] = []
    if "WRONG_SEQUENCE" in issue_types:
        recommendations.append("Повторить сценарий с фокусом на порядок операций.")
    if "LATE_ACTION" in issue_types:
        recommendations.append("Повторить тренировку с контролем времени реакции.")
    if "MISSED_ACTION" in issue_types:
        recommendations.append("Отработать выполнение всех обязательных шагов сценария.")
    if "WRONG_ACTION" in issue_types:
        recommendations.append("Повторить работу с командами оборудования и уставками.")
    if not recommendations:
        recommendations.append("Закрепить результат повторным прохождением сценария.")

    headline = (
        f"Результат {outcome.result.score:.0f}/{outcome.result.max_score:.0f}; "
        f"ошибок: {outcome.result.error_count}."
    )
    return DebriefResponse(
        session_id=session_id,
        status=outcome.result.status,
        generated_by="rules",
        headline=headline,
        strengths=strengths,
        issues=issue_types,
        recommendations=recommendations,
    )


@router.get(
    "/operators/{operator_id}/training-results",
    response_model=TrainingResultListResponse,
)
async def get_operator_training_results(
    operator_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TrainingResultListResponse:
    del admin
    await _require_operator_target(session, operator_id)
    results = await TrainingInsightsService(session).list_results(operator_id)
    return TrainingResultListResponse(
        items=[TrainingResultResponse.model_validate(item) for item in results]
    )


@router.get(
    "/operators/{operator_id}/skill-profile",
    response_model=SkillProfileResponse,
)
async def get_operator_skill_profile(
    operator_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SkillProfileResponse:
    del admin
    await _require_operator_target(session, operator_id)
    profile = await TrainingInsightsService(session).build_skill_profile(operator_id)
    return SkillProfileResponse(
        operator_id=profile.operator_id,
        assessed_sessions=profile.assessed_sessions,
        average_score=profile.average_score,
        average_sequence_score=profile.average_sequence_score,
        average_reaction_score=profile.average_reaction_score,
        average_safety_score=profile.average_safety_score,
        error_counts=profile.error_counts,
        weakest_skill=profile.weakest_skill,
        recent_scores=profile.recent_scores,
    )


@router.get(
    "/operators/{operator_id}/recommendations",
    response_model=TrainingRecommendationsResponse,
)
async def get_operator_recommendations(
    operator_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TrainingRecommendationsResponse:
    del admin
    await _require_operator_target(session, operator_id)
    items = await TrainingInsightsService(session).build_recommendations(operator_id)
    return TrainingRecommendationsResponse(
        operator_id=operator_id,
        source="rules",
        items=[
            TrainingRecommendationResponse(
                focus=item.focus,
                priority=item.priority,
                reason=item.reason,
            )
            for item in items
        ],
    )
