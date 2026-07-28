from typing import Annotated

from fastapi import Depends, Header, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.integrations.simulation.base import SimulationGateway
from app.integrations.simulation.factory import create_simulation_gateway
from app.models import User, UserRole
from app.repositories.users import UserRepository
from app.security.tokens import TokenError, decode_access_token


def unauthorized() -> ApiError:
    return ApiError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="UNAUTHENTICATED",
        message="Требуется вход в систему",
    )


async def current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    if authorization is None:
        raise unauthorized()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized()

    try:
        user_id = decode_access_token(token, settings)
    except TokenError as exc:
        raise unauthorized() from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise unauthorized()

    return user


async def require_admin(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != UserRole.ADMIN:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="Недостаточно прав",
        )
    return user


async def require_operator(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != UserRole.OPERATOR:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="Недостаточно прав",
        )
    return user


def get_simulation_gateway(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SimulationGateway:
    return create_simulation_gateway(settings)


async def websocket_current_user(
    websocket: WebSocket,
    session: AsyncSession,
    settings: Settings,
) -> User:
    token = websocket.query_params.get("access_token")
    if token is None:
        raise unauthorized()
    try:
        user_id = decode_access_token(token, settings)
    except TokenError as exc:
        raise unauthorized() from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise unauthorized()
    return user
