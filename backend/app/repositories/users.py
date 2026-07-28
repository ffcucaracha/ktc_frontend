from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginEvent, User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_operator_by_id(self, operator_id: UUID) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == operator_id, User.role == UserRole.OPERATOR),
        )
        return result.scalar_one_or_none()

    async def list_operators(
        self,
        limit: int,
        offset: int,
        username: str | None,
        full_name: str | None,
        is_active: bool | None,
    ) -> tuple[list[User], int]:
        filters = [User.role == UserRole.OPERATOR]
        if username:
            filters.append(User.username.ilike(f"%{username}%"))
        if full_name:
            filters.append(User.full_name.ilike(f"%{full_name}%"))
        if is_active is not None:
            filters.append(User.is_active == is_active)

        total = await self._session.scalar(select(func.count()).select_from(User).where(*filters))
        result = await self._session.execute(
            select(User)
            .where(*filters)
            .order_by(User.username.asc(), User.id.asc())
            .limit(limit)
            .offset(offset),
        )
        return list(result.scalars()), total or 0

    async def create_admin(self, username: str, full_name: str, password_hash: str) -> User:
        user = User(
            username=username,
            full_name=full_name,
            role=UserRole.ADMIN,
            password_hash=password_hash,
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def create_operator(self, username: str, full_name: str, password_hash: str) -> User:
        user = User(
            username=username,
            full_name=full_name,
            role=UserRole.OPERATOR,
            password_hash=password_hash,
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def count_successful_logins(self, operator_id: UUID) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(LoginEvent)
            .where(LoginEvent.user_id == operator_id, LoginEvent.success.is_(True)),
        )
        return total or 0

    async def last_successful_login_at(self, operator_id: UUID) -> datetime | None:
        value = await self._session.scalar(
            select(func.max(LoginEvent.occurred_at)).where(
                LoginEvent.user_id == operator_id,
                LoginEvent.success.is_(True),
            ),
        )
        if value is not None and not isinstance(value, datetime):
            raise TypeError("Unexpected login timestamp type")
        return value

    async def list_login_history(
        self,
        operator_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[LoginEvent], int]:
        filters = [LoginEvent.user_id == operator_id]
        total = await self._session.scalar(
            select(func.count()).select_from(LoginEvent).where(*filters),
        )
        result = await self._session.execute(
            select(LoginEvent)
            .where(*filters)
            .order_by(LoginEvent.occurred_at.desc(), LoginEvent.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return list(result.scalars()), total or 0
