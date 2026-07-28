from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_user
from app.api.errors import ApiError
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.auth import AccessTokenResponse, LoginRequest, MeResponse, UserResponse
from app.services.auth import AuthService, InvalidCredentialsError, InvalidRefreshTokenError

REFRESH_COOKIE_NAME = "refresh_token"
MAX_USER_AGENT_LENGTH = 512

router = APIRouter(prefix="/auth", tags=["auth"])


def extract_ip_address(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def extract_user_agent(request: Request) -> str | None:
    user_agent = request.headers.get("user-agent")
    if user_agent is None:
        return None
    return user_agent[:MAX_USER_AGENT_LENGTH]


def set_refresh_cookie(response: Response, refresh_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def invalid_login_error() -> ApiError:
    return ApiError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="INVALID_CREDENTIALS",
        message="Неверное имя пользователя или пароль",
    )


def invalid_refresh_error() -> ApiError:
    return ApiError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="UNAUTHENTICATED",
        message="Требуется вход в систему",
    )


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessTokenResponse:
    service = AuthService(session, settings)
    try:
        tokens = await service.login(
            username=payload.username,
            password=payload.password,
            ip_address=extract_ip_address(request),
            user_agent=extract_user_agent(request),
        )
    except InvalidCredentialsError as exc:
        raise invalid_login_error() from exc

    set_refresh_cookie(response, tokens.refresh_token, settings)
    return AccessTokenResponse(access_token=tokens.access_token)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> AccessTokenResponse:
    if refresh_token is None:
        raise invalid_refresh_error()

    service = AuthService(session, settings)
    try:
        tokens = await service.refresh(refresh_token)
    except InvalidRefreshTokenError as exc:
        clear_refresh_cookie(response, settings)
        raise invalid_refresh_error() from exc

    set_refresh_cookie(response, tokens.refresh_token, settings)
    return AccessTokenResponse(access_token=tokens.access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> None:
    service = AuthService(session, settings)
    await service.logout(refresh_token)
    clear_refresh_cookie(response, settings)


@router.get("/me", response_model=MeResponse)
async def me(user: Annotated[User, Depends(current_user)]) -> MeResponse:
    return MeResponse(user=UserResponse.model_validate(user))
