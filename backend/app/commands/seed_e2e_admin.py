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
    operator_username = os.getenv("E2E_OPERATOR_USERNAME", DEFAULT_E2E_OPERATOR_USERNAME)
    operator_full_name = os.getenv("E2E_OPERATOR_FULL_NAME", DEFAULT_E2E_OPERATOR_FULL_NAME)

    admin = await seed_e2e_admin(
        session_factory=AsyncSessionLocal,
        username=admin_username,
        full_name=admin_full_name,
        password=admin_password,
    )
    operator = await seed_e2e_operator(
        session_factory=AsyncSessionLocal,
        username=operator_username,
        full_name=operator_full_name,
        password=operator_password,
    )
    print(f"E2E users are ready: {admin.username}, {operator.username}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
