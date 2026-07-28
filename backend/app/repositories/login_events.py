from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginEvent, LoginFailureReason, User


class LoginEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_success(
        self,
        user: User,
        username_entered: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> LoginEvent:
        event = LoginEvent(
            user_id=user.id,
            username_entered=username_entered,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def record_failure(
        self,
        user: User | None,
        username_entered: str,
        failure_reason: LoginFailureReason,
        ip_address: str | None,
        user_agent: str | None,
    ) -> LoginEvent:
        event = LoginEvent(
            user_id=user.id if user is not None else None,
            username_entered=username_entered,
            success=False,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(event)
        await self._session.flush()
        return event
