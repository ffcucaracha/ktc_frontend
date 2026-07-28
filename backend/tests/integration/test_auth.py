from datetime import timedelta
from typing import Annotated

import pytest
from fastapi import Depends
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.dependencies import require_admin, require_operator
from app.core.time import utc_now
from app.models import LoginEvent, LoginFailureReason, RefreshToken, User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import hash_refresh_token


async def create_user(
    session_factory: async_sessionmaker,
    username: str,
    password: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    async with session_factory() as session:
        user = User(
            username=username,
            full_name=f"{username} User",
            role=role,
            password_hash=hash_password(password),
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        return user


def get_refresh_cookie(client: AsyncClient) -> str:
    cookie = client.cookies.get("refresh_token")
    assert cookie is not None
    return cookie


@pytest.mark.asyncio
async def test_success_login_sets_refresh_cookie_and_records_event(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    await create_user(postgres_session_factory, "operator", "secret", UserRole.OPERATOR)

    response = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "secret"},
        headers={"user-agent": "pytest-agent"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert app_client.cookies.get("refresh_token") is not None

    async with postgres_session_factory() as session:
        login_event = await session.scalar(select(LoginEvent))
        refresh_count = await session.scalar(select(func.count()).select_from(RefreshToken))

    assert login_event is not None
    assert login_event.success is True
    assert login_event.username_entered == "operator"
    assert login_event.user_agent == "pytest-agent"
    assert refresh_count == 1


@pytest.mark.asyncio
async def test_invalid_password_and_unknown_username_share_generic_response(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    await create_user(postgres_session_factory, "operator", "secret", UserRole.OPERATOR)

    invalid_password = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "wrong"},
    )
    unknown_username = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "missing", "password": "wrong"},
    )

    assert invalid_password.status_code == 401
    assert unknown_username.status_code == 401
    assert invalid_password.json() == unknown_username.json()
    assert invalid_password.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async with postgres_session_factory() as session:
        events = (await session.execute(select(LoginEvent))).scalars().all()

    assert len(events) == 2
    assert {event.success for event in events} == {False}
    assert {event.failure_reason for event in events} == {
        LoginFailureReason.INVALID_CREDENTIALS,
    }


@pytest.mark.asyncio
async def test_inactive_user_cannot_login_and_event_is_recorded(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    await create_user(
        postgres_session_factory,
        "inactive",
        "secret",
        UserRole.OPERATOR,
        is_active=False,
    )

    response = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "inactive", "password": "secret"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async with postgres_session_factory() as session:
        login_event = await session.scalar(select(LoginEvent))

    assert login_event is not None
    assert login_event.success is False
    assert login_event.failure_reason == LoginFailureReason.INACTIVE_USER


@pytest.mark.asyncio
async def test_refresh_rotates_and_reuse_old_refresh_token_fails(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    await create_user(postgres_session_factory, "operator", "secret", UserRole.OPERATOR)
    login_response = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "secret"},
    )
    assert login_response.status_code == 200
    old_refresh_token = get_refresh_cookie(app_client)

    refresh_response = await app_client.post("/api/v1/auth/refresh")

    assert refresh_response.status_code == 200
    new_refresh_token = get_refresh_cookie(app_client)
    assert new_refresh_token != old_refresh_token

    async with postgres_session_factory() as session:
        old_token_row = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(old_refresh_token),
            ),
        )
        new_token_row = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(new_refresh_token),
            ),
        )

    assert old_token_row is not None
    assert old_token_row.revoked_at is not None
    assert new_token_row is not None
    assert old_token_row.replaced_by_id == new_token_row.id

    app_client.cookies.set("refresh_token", old_refresh_token)
    reuse_response = await app_client.post("/api/v1/auth/refresh")

    assert reuse_response.status_code == 401
    assert reuse_response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    user = await create_user(postgres_session_factory, "operator", "secret", UserRole.OPERATOR)
    login_response = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "secret"},
    )
    assert login_response.status_code == 200

    async with postgres_session_factory() as session:
        db_user = await session.get(User, user.id)
        assert db_user is not None
        db_user.is_active = False
        await session.commit()

    response = await app_client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    await create_user(postgres_session_factory, "operator", "secret", UserRole.OPERATOR)
    await app_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "secret"},
    )
    refresh_token = get_refresh_cookie(app_client)

    response = await app_client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert "refresh_token" not in app_client.cookies
    async with postgres_session_factory() as session:
        token_row = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh_token),
            ),
        )

    assert token_row is not None
    assert token_row.revoked_at is not None


@pytest.mark.asyncio
async def test_me_returns_current_user(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    user = await create_user(postgres_session_factory, "operator", "secret", UserRole.OPERATOR)
    login_response = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "secret"},
    )
    access_token = login_response.json()["access_token"]

    response = await app_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(user.id)
    assert response.json()["user"]["role"] == "operator"


@pytest.mark.asyncio
async def test_role_dependencies(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    await create_user(postgres_session_factory, "admin", "secret", UserRole.ADMIN)
    await create_user(postgres_session_factory, "operator", "secret", UserRole.OPERATOR)

    async def admin_probe(user: Annotated[User, Depends(require_admin)]) -> dict[str, bool]:
        return {"ok": user.role == UserRole.ADMIN}

    async def operator_probe(user: Annotated[User, Depends(require_operator)]) -> dict[str, bool]:
        return {"ok": user.role == UserRole.OPERATOR}

    app_client._transport.app.get("/test/admin")(admin_probe)
    app_client._transport.app.get("/test/operator")(operator_probe)

    admin_login = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "secret"},
    )
    admin_token = admin_login.json()["access_token"]
    app_client.cookies.clear()
    operator_login = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "secret"},
    )
    operator_token = operator_login.json()["access_token"]

    admin_allowed = await app_client.get(
        "/test/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    operator_forbidden = await app_client.get(
        "/test/admin",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    operator_allowed = await app_client.get(
        "/test/operator",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    admin_forbidden = await app_client.get(
        "/test/operator",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert admin_allowed.status_code == 200
    assert operator_forbidden.status_code == 403
    assert operator_allowed.status_code == 200
    assert admin_forbidden.status_code == 403


@pytest.mark.asyncio
async def test_expired_refresh_token_is_rejected(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    user = await create_user(postgres_session_factory, "operator", "secret", UserRole.OPERATOR)
    raw_refresh_token = "expired-token"

    async with postgres_session_factory() as session:
        session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(raw_refresh_token),
                expires_at=utc_now() - timedelta(days=1),
            ),
        )
        await session.commit()

    app_client.cookies.set("refresh_token", raw_refresh_token)
    response = await app_client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
