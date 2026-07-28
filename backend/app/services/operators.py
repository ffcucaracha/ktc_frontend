from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginEvent, User
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.security.passwords import generate_temporary_password, hash_password


class OperatorNotFoundError(Exception):
    pass


class DuplicateUsernameError(Exception):
    pass


@dataclass(frozen=True)
class OperatorList:
    items: list[User]
    total: int


@dataclass(frozen=True)
class OperatorCreateResult:
    operator: User
    temporary_password: str | None


@dataclass(frozen=True)
class OperatorResetPasswordResult:
    operator: User
    temporary_password: str


@dataclass(frozen=True)
class LoginHistory:
    items: list[LoginEvent]
    total: int


@dataclass(frozen=True)
class LoginStats:
    successful_count: int
    last_successful_login_at: datetime | None


class OperatorService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)

    async def list_operators(
        self,
        limit: int,
        offset: int,
        username: str | None,
        full_name: str | None,
        is_active: bool | None,
    ) -> OperatorList:
        items, total = await self._users.list_operators(
            limit=limit,
            offset=offset,
            username=username,
            full_name=full_name,
            is_active=is_active,
        )
        return OperatorList(items=items, total=total)

    async def get_operator(self, operator_id: UUID) -> User:
        operator = await self._users.get_operator_by_id(operator_id)
        if operator is None:
            raise OperatorNotFoundError
        return operator

    async def create_operator(
        self,
        username: str,
        full_name: str,
        password: str | None,
    ) -> OperatorCreateResult:
        if await self._users.get_by_username(username) is not None:
            raise DuplicateUsernameError

        temporary_password = password or generate_temporary_password()
        try:
            operator = await self._users.create_operator(
                username=username,
                full_name=full_name,
                password_hash=hash_password(temporary_password),
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateUsernameError from exc

        return OperatorCreateResult(
            operator=operator,
            temporary_password=None if password else temporary_password,
        )

    async def update_operator(
        self,
        operator_id: UUID,
        username: str | None,
        full_name: str | None,
        is_active: bool | None,
    ) -> User:
        operator = await self.get_operator(operator_id)

        if username is not None and username != operator.username:
            existing_user = await self._users.get_by_username(username)
            if existing_user is not None:
                raise DuplicateUsernameError
            operator.username = username

        if full_name is not None:
            operator.full_name = full_name

        if is_active is not None and is_active != operator.is_active:
            operator.is_active = is_active
            if not is_active:
                await self._refresh_tokens.revoke_user_tokens(operator.id)

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateUsernameError from exc

        return operator

    async def reset_password(self, operator_id: UUID) -> OperatorResetPasswordResult:
        operator = await self.get_operator(operator_id)
        temporary_password = generate_temporary_password()
        operator.password_hash = hash_password(temporary_password)
        await self._refresh_tokens.revoke_user_tokens(operator.id)
        await self._session.commit()
        return OperatorResetPasswordResult(
            operator=operator,
            temporary_password=temporary_password,
        )

    async def login_history(self, operator_id: UUID, limit: int, offset: int) -> LoginHistory:
        await self.get_operator(operator_id)
        items, total = await self._users.list_login_history(
            operator_id=operator_id,
            limit=limit,
            offset=offset,
        )
        return LoginHistory(items=items, total=total)

    async def login_stats(self, operator_id: UUID) -> LoginStats:
        await self.get_operator(operator_id)
        successful_count = await self._users.count_successful_logins(operator_id)
        last_successful_login_at = await self._users.last_successful_login_at(operator_id)
        return LoginStats(
            successful_count=successful_count,
            last_successful_login_at=last_successful_login_at,
        )
