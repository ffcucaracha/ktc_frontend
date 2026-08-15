from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_operator
from app.api.errors import ApiError
from app.db.session import get_session
from app.models import User
from app.schemas.assessment import (
    OperatorErrorResponse,
    TrainingAssessmentResponse,
    TrainingResultResponse,
)
from app.services.assessment import (
    AssessmentOutcome,
    AssessmentScenarioRequiredError,
    AssessmentService,
    AssessmentSessionNotFoundError,
)

router = APIRouter(tags=["assessment"])


def _session_not_found() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", "Сессия не найдена")


def _scenario_required() -> ApiError:
    return ApiError(
        status.HTTP_409_CONFLICT,
        "TRAINING_SCENARIO_REQUIRED",
        "Для оценки сессия должна быть запущена с учебным сценарием",
    )


def _response(outcome: AssessmentOutcome) -> TrainingAssessmentResponse:
    return TrainingAssessmentResponse(
        result=TrainingResultResponse.model_validate(outcome.result),
        errors=[OperatorErrorResponse.model_validate(item) for item in outcome.errors],
    )


@router.post(
    "/simulation-sessions/{session_id}/assessment",
    response_model=TrainingAssessmentResponse,
)
async def calculate_assessment(
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
    return _response(outcome)


@router.get(
    "/simulation-sessions/{session_id}/assessment",
    response_model=TrainingAssessmentResponse,
)
async def get_assessment(
    session_id: UUID,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TrainingAssessmentResponse:
    try:
        outcome = await AssessmentService(session).get_assessment(session_id, operator.id)
    except AssessmentSessionNotFoundError as exc:
        raise _session_not_found() from exc
    except AssessmentScenarioRequiredError as exc:
        raise _scenario_required() from exc
    return _response(outcome)
