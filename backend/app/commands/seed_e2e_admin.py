import asyncio
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import AsyncSessionLocal
from app.models import User, UserRole
from app.repositories.users import UserRepository
from app.security.passwords import hash_password

DEFAULT_E2E_ADMIN_USERNAME = "e2e-admin"
DEFAULT_E2E_ADMIN_FULL_NAME = "E2E Administrator"
DEFAULT_E2E_ADMIN_PASSWORD = "change-me-e2e-admin-password"
DEFAULT_E2E_OPERATOR_USERNAME = "e2e-operator"
DEFAULT_E2E_OPERATOR_FULL_NAME = "E2E Operator"
DEFAULT_E2E_OPERATOR_PASSWORD = "change-me-e2e-operator-password"
DEFAULT_E2E_OPERATOR_COUNT = 5


def _operator_username(base_username: str, index: int) -> str:
    if index == 1:
        return base_username
    return f"{base_username}-{index:02d}"


def _operator_full_name(base_full_name: str, index: int) -> str:
    if index == 1:
        return base_full_name
    return f"{base_full_name} {index:02d}"


async def seed_e2e_admin(
    session_factory: async_sessionmaker[AsyncSession],
    username: str,
    full_name: str,
    password: str,
) -> User:
    password_hash = hash_password(password)
    async with session_factory() as session:
        repository = UserRepository(session)
        user = await repository.get_by_username(username)
        if user is None:
            user = await repository.create_admin(
                username=username,
                full_name=full_name,
                password_hash=password_hash,
            )
        else:
            user.full_name = full_name
            user.role = UserRole.ADMIN
            user.password_hash = password_hash
            user.is_active = True
        await session.commit()
        return user


async def seed_e2e_operator(
    session_factory: async_sessionmaker[AsyncSession],
    username: str,
    full_name: str,
    password: str,
) -> User:
    password_hash = hash_password(password)
    async with session_factory() as session:
        repository = UserRepository(session)
        user = await repository.get_by_username(username)
        if user is None:
            user = await repository.create_operator(
                username=username,
                full_name=full_name,
                password_hash=password_hash,
            )
        else:
            user.full_name = full_name
            user.role = UserRole.OPERATOR
            user.password_hash = password_hash
            user.is_active = True
        await session.commit()
        return user


async def run() -> None:
    admin_password = os.getenv("E2E_ADMIN_PASSWORD", DEFAULT_E2E_ADMIN_PASSWORD)
    admin_username = os.getenv("E2E_ADMIN_USERNAME", DEFAULT_E2E_ADMIN_USERNAME)
    admin_full_name = os.getenv("E2E_ADMIN_FULL_NAME", DEFAULT_E2E_ADMIN_FULL_NAME)
    operator_password = os.getenv("E2E_OPERATOR_PASSWORD", DEFAULT_E2E_OPERATOR_PASSWORD)
    operator_base_username = os.getenv("E2E_OPERATOR_USERNAME", DEFAULT_E2E_OPERATOR_USERNAME)
    operator_base_full_name = os.getenv("E2E_OPERATOR_FULL_NAME", DEFAULT_E2E_OPERATOR_FULL_NAME)
    operator_count = max(1, int(os.getenv("E2E_OPERATOR_COUNT", str(DEFAULT_E2E_OPERATOR_COUNT))))

    admin = await seed_e2e_admin(
        session_factory=AsyncSessionLocal,
        username=admin_username,
        full_name=admin_full_name,
        password=admin_password,
    )

    operators: list[User] = []
    for index in range(1, operator_count + 1):
        # Preserve the legacy e2e-operator account as operator #1 so Selenium smoke tests
        # and manual demo logins keep working. Additional operators get stable suffixes.
        username = _operator_username(operator_base_username, index)
        full_name = _operator_full_name(operator_base_full_name, index)
        operators.append(
            await seed_e2e_operator(
                session_factory=AsyncSessionLocal,
                username=username,
                full_name=full_name,
                password=operator_password,
            )
        )

    usernames = ", ".join(item.username for item in operators)
    print(f"E2E users are ready: admin={admin.username}; operators={usernames}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
