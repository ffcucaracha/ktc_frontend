import argparse
import asyncio
import os
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import AsyncSessionLocal
from app.models import User
from app.repositories.users import UserRepository
from app.security.passwords import generate_temporary_password, hash_password

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_FULL_NAME = "System Administrator"


@dataclass(frozen=True)
class CreateAdminResult:
    user: User
    created: bool
    temporary_password: str | None


async def create_admin(
    session_factory: async_sessionmaker[AsyncSession],
    username: str,
    full_name: str,
    password: str | None,
) -> CreateAdminResult:
    temporary_password = password or generate_temporary_password()
    password_hash = hash_password(temporary_password)

    async with session_factory() as session:
        repository = UserRepository(session)
        existing_user = await repository.get_by_username(username)
        if existing_user is not None:
            return CreateAdminResult(
                user=existing_user,
                created=False,
                temporary_password=None,
            )

        user = await repository.create_admin(
            username=username,
            full_name=full_name,
            password_hash=password_hash,
        )
        await session.commit()

    return CreateAdminResult(
        user=user,
        created=True,
        temporary_password=None if password else temporary_password,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the initial admin user.")
    parser.add_argument("--username", default=os.getenv("ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME))
    parser.add_argument(
        "--full-name",
        default=os.getenv("ADMIN_FULL_NAME", DEFAULT_ADMIN_FULL_NAME),
    )
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    result = await create_admin(
        session_factory=AsyncSessionLocal,
        username=args.username,
        full_name=args.full_name,
        password=os.getenv("ADMIN_PASSWORD"),
    )

    if not result.created:
        print(f"Admin user already exists: {result.user.username}")
        return

    print(f"Admin user created: {result.user.username}")
    if result.temporary_password is not None:
        print(f"Temporary password: {result.temporary_password}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
