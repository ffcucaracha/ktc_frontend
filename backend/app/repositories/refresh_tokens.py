from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash),
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: object,
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(refresh_token)
        await self._session.flush()
        return refresh_token

    def revoke(self, refresh_token: RefreshToken) -> None:
        refresh_token.revoked_at = utc_now()

    async def revoke_user_tokens(self, user_id: UUID) -> None:
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            ),
        )
        for refresh_token in result.scalars():
            self.revoke(refresh_token)
