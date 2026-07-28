from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_session
from app.main import create_app


class FakeSession:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def execute(self, statement: object) -> None:
        if self.should_fail:
            raise RuntimeError("database unavailable")


async def healthy_session() -> AsyncIterator[FakeSession]:
    yield FakeSession()


async def unhealthy_session() -> AsyncIterator[FakeSession]:
    yield FakeSession(should_fail=True)


@pytest.mark.asyncio
async def test_live_returns_ok() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_returns_ok_when_database_is_available() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = healthy_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_returns_503_when_database_is_unavailable() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = unhealthy_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "DATABASE_UNAVAILABLE"
