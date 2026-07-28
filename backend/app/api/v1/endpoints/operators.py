from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.api.errors import ApiError
from app.db.session import get_session
from app.models import LoginEvent, User
from app.schemas.auth import UserResponse
from app.schemas.operators import (
    LoginHistoryItem,
    LoginHistoryResponse,
    LoginStatsResponse,
    OperatorCreateRequest,
    OperatorCreateResponse,
    OperatorListResponse,
    OperatorPatchRequest,
    OperatorResetPasswordResponse,
)
from app.services.operators import (
    DuplicateUsernameError,
    OperatorNotFoundError,
    OperatorService,
)

router = APIRouter(prefix="/operators", tags=["operators"])


def operator_not_found_error() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="OPERATOR_NOT_FOUND",
        message="Оператор не найден",
    )


def duplicate_username_error() -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        code="USERNAME_ALREADY_EXISTS",
        message="Пользователь с таким именем уже существует",  # noqa: RUF001
    )


def to_login_history_item(event: LoginEvent) -> LoginHistoryItem:
    return LoginHistoryItem.model_validate(
        {
            "id": event.id,
            "occurred_at": event.occurred_at,
            "success": event.success,
            "failure_reason": event.failure_reason,
            "ip_address": str(event.ip_address) if event.ip_address is not None else None,
            "user_agent": event.user_agent,
        },
    )


@router.get("", response_model=OperatorListResponse)
async def list_operators(
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    username: Annotated[str | None, Query(max_length=64)] = None,
    full_name: Annotated[str | None, Query(max_length=255)] = None,
    is_active: bool | None = None,
) -> OperatorListResponse:
    del admin
    result = await OperatorService(session).list_operators(
        limit=limit,
        offset=offset,
        username=username,
        full_name=full_name,
        is_active=is_active,
    )
    return OperatorListResponse(
        items=[UserResponse.model_validate(operator) for operator in result.items],
        total=result.total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=OperatorCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_operator(
    payload: OperatorCreateRequest,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperatorCreateResponse:
    del admin
    try:
        result = await OperatorService(session).create_operator(
            username=payload.username,
            full_name=payload.full_name,
            password=payload.password,
        )
    except DuplicateUsernameError as exc:
        raise duplicate_username_error() from exc

    return OperatorCreateResponse(
        operator=UserResponse.model_validate(result.operator),
        temporary_password=result.temporary_password,
    )


@router.get("/{operator_id}", response_model=UserResponse)
async def get_operator(
    operator_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    del admin
    try:
        operator = await OperatorService(session).get_operator(operator_id)
    except OperatorNotFoundError as exc:
        raise operator_not_found_error() from exc
    return UserResponse.model_validate(operator)


@router.patch("/{operator_id}", response_model=UserResponse)
async def patch_operator(
    operator_id: UUID,
    payload: OperatorPatchRequest,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    del admin
    try:
        operator = await OperatorService(session).update_operator(
            operator_id=operator_id,
            username=payload.username,
            full_name=payload.full_name,
            is_active=payload.is_active,
        )
    except OperatorNotFoundError as exc:
        raise operator_not_found_error() from exc
    except DuplicateUsernameError as exc:
        raise duplicate_username_error() from exc
    return UserResponse.model_validate(operator)


@router.post("/{operator_id}/reset-password", response_model=OperatorResetPasswordResponse)
async def reset_operator_password(
    operator_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperatorResetPasswordResponse:
    del admin
    try:
        result = await OperatorService(session).reset_password(operator_id)
    except OperatorNotFoundError as exc:
        raise operator_not_found_error() from exc
    return OperatorResetPasswordResponse(
        operator=UserResponse.model_validate(result.operator),
        temporary_password=result.temporary_password,
    )


@router.get("/{operator_id}/login-history", response_model=LoginHistoryResponse)
async def operator_login_history(
    operator_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LoginHistoryResponse:
    del admin
    try:
        result = await OperatorService(session).login_history(operator_id, limit, offset)
    except OperatorNotFoundError as exc:
        raise operator_not_found_error() from exc
    return LoginHistoryResponse(
        items=[to_login_history_item(item) for item in result.items],
        total=result.total,
        limit=limit,
        offset=offset,
    )


@router.get("/{operator_id}/login-stats", response_model=LoginStatsResponse)
async def operator_login_stats(
    operator_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LoginStatsResponse:
    del admin
    try:
        result = await OperatorService(session).login_stats(operator_id)
    except OperatorNotFoundError as exc:
        raise operator_not_found_error() from exc
    return LoginStatsResponse(
        successful_count=result.successful_count,
        last_successful_login_at=result.last_successful_login_at,
    )
