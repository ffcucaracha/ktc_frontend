from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.time import utc_now
from app.models import LoginFailureReason, RefreshToken, User
from app.repositories.login_events import LoginEventRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.security.passwords import verify_password
from app.security.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)
        self._login_events = LoginEventRepository(session)

    async def login(
        self,
        username: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> AuthTokens:
        user = await self._users.get_by_username(username)

        if user is None or not verify_password(password, user.password_hash):
            await self._login_events.record_failure(
                user=None,
                username_entered=username,
                failure_reason=LoginFailureReason.INVALID_CREDENTIALS,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await self._session.commit()
            raise InvalidCredentialsError

        if not user.is_active:
            await self._login_events.record_failure(
                user=user,
                username_entered=username,
                failure_reason=LoginFailureReason.INACTIVE_USER,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await self._session.commit()
            raise InvalidCredentialsError

        tokens = await self._issue_tokens(user)
        await self._login_events.record_success(
            user=user,
            username_entered=username,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._session.commit()
        return tokens

    async def refresh(self, raw_refresh_token: str) -> AuthTokens:
        refresh_token = await self._get_valid_refresh_token(raw_refresh_token)
        user = await self._users.get_by_id(refresh_token.user_id)
        if user is None or not user.is_active:
            self._refresh_tokens.revoke(refresh_token)
            await self._session.commit()
            raise InvalidRefreshTokenError

        new_tokens = await self._issue_tokens(user)
        new_refresh_token = await self._refresh_tokens.get_by_hash(
            hash_refresh_token(new_tokens.refresh_token),
        )
        if new_refresh_token is None:
            raise InvalidRefreshTokenError

        self._refresh_tokens.revoke(refresh_token)
        refresh_token.replaced_by_id = new_refresh_token.id
        await self._session.commit()
        return new_tokens

    async def logout(self, raw_refresh_token: str | None) -> None:
        if raw_refresh_token is None:
            return

        refresh_token = await self._refresh_tokens.get_by_hash(
            hash_refresh_token(raw_refresh_token),
        )
        if refresh_token is not None and refresh_token.revoked_at is None:
            self._refresh_tokens.revoke(refresh_token)
            await self._session.commit()

    async def _issue_tokens(self, user: User) -> AuthTokens:
        access_token = create_access_token(user.id, self._settings)
        refresh_token = generate_refresh_token()
        expires_at = utc_now() + timedelta(days=self._settings.refresh_token_ttl_days)
        await self._refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
        )
        return AuthTokens(access_token=access_token, refresh_token=refresh_token)

    async def _get_valid_refresh_token(self, raw_refresh_token: str) -> RefreshToken:
        refresh_token = await self._refresh_tokens.get_by_hash(
            hash_refresh_token(raw_refresh_token),
        )
        if (
            refresh_token is None
            or refresh_token.revoked_at is not None
            or refresh_token.expires_at <= utc_now()
        ):
            raise InvalidRefreshTokenError
        return refresh_token
