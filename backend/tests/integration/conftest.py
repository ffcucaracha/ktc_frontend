import asyncio
import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.core.config import get_settings
from app.db.session import get_session
from app.main import create_app

DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://trainer:trainer@localhost:5432/trainer"


async def can_connect(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def postgres_database_url() -> str:
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Set RUN_POSTGRES_TESTS=1 to run PostgreSQL integration tests.")

    database_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    try:
        asyncio.run(asyncio.wait_for(can_connect(database_url), timeout=3))
    except Exception as exc:
        pytest.skip(f"PostgreSQL is not available: {exc}")
    return database_url


@pytest.fixture()
def migrated_database(postgres_database_url: str) -> Iterator[str]:
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = postgres_database_url
    get_settings.cache_clear()

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    try:
        yield postgres_database_url
    finally:
        command.downgrade(config, "base")
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()


@pytest.fixture()
async def postgres_session_factory(
    migrated_database: str,
) -> async_sessionmaker:
    engine = create_async_engine(migrated_database)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture()
async def app_client(
    postgres_session_factory: async_sessionmaker,
) -> AsyncClient:
    app = create_app()

    async def override_session():
        async with postgres_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
