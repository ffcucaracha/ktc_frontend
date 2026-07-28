from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.time import utc_now
from app.models import LoginEvent, LoginFailureReason, RefreshToken, User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import hash_refresh_token


async def create_user(
    session_factory: async_sessionmaker,
    username: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    async with session_factory() as session:
        user = User(
            username=username,
            full_name=f"{username} Full Name",
            role=role,
            password_hash=hash_password("secret-password"),
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        return user


async def admin_headers(
    app_client: AsyncClient,
    session_factory: async_sessionmaker,
) -> dict[str, str]:
    await create_user(session_factory, "admin", UserRole.ADMIN)
    response = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "secret-password"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_operator_requires_admin_and_returns_password_once(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    operator = await create_user(postgres_session_factory, "operator-user", UserRole.OPERATOR)
    operator_login = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "operator-user", "password": "secret-password"},
    )
    operator_headers = {"Authorization": f"Bearer {operator_login.json()['access_token']}"}

    forbidden = await app_client.post(
        "/api/v1/operators",
        json={"username": "created", "full_name": "Created Operator"},
        headers=operator_headers,
    )
    assert forbidden.status_code == 403

    headers = await admin_headers(app_client, postgres_session_factory)
    response = await app_client.post(
        "/api/v1/operators",
        json={"username": "created", "full_name": "Created Operator"},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["operator"]["username"] == "created"
    assert body["operator"]["role"] == "operator"
    assert "password_hash" not in body["operator"]
    assert "refresh_token" not in body["operator"]
    assert len(body["temporary_password"]) == 24

    detail = await app_client.get(f"/api/v1/operators/{body['operator']['id']}", headers=headers)
    assert detail.status_code == 200
    assert "temporary_password" not in detail.json()
    assert detail.json()["id"] == body["operator"]["id"]
    assert detail.json()["role"] == "operator"
    assert detail.json()["id"] != str(operator.id)


@pytest.mark.asyncio
async def test_create_operator_with_provided_password_does_not_return_it(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    headers = await admin_headers(app_client, postgres_session_factory)

    response = await app_client.post(
        "/api/v1/operators",
        json={
            "username": "provided",
            "full_name": "Provided Password",
            "password": "provided-password",
        },
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["temporary_password"] is None

    login_response = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "provided", "password": "provided-password"},
    )
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_duplicate_username_returns_409(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    headers = await admin_headers(app_client, postgres_session_factory)
    await create_user(postgres_session_factory, "duplicate", UserRole.OPERATOR)

    response = await app_client.post(
        "/api/v1/operators",
        json={"username": "duplicate", "full_name": "Duplicate Operator"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_list_operators_filters_and_stable_pagination(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    headers = await admin_headers(app_client, postgres_session_factory)
    await create_user(postgres_session_factory, "alpha", UserRole.OPERATOR)
    await create_user(postgres_session_factory, "beta", UserRole.OPERATOR, is_active=False)
    await create_user(postgres_session_factory, "gamma", UserRole.OPERATOR)
    await create_user(postgres_session_factory, "not-listed-admin", UserRole.ADMIN)

    response = await app_client.get(
        "/api/v1/operators",
        params={"limit": 2, "offset": 0},
        headers=headers,
    )
    filtered = await app_client.get(
        "/api/v1/operators",
        params={"username": "a", "is_active": True},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert [item["username"] for item in body["items"]] == ["alpha", "beta"]
    assert filtered.status_code == 200
    assert [item["username"] for item in filtered.json()["items"]] == ["alpha", "gamma"]


@pytest.mark.asyncio
async def test_patch_operator_updates_allowed_fields_and_deactivation_revokes_tokens(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    headers = await admin_headers(app_client, postgres_session_factory)
    operator = await create_user(postgres_session_factory, "patch-me", UserRole.OPERATOR)
    raw_refresh_token = "operator-refresh-token"
    async with postgres_session_factory() as session:
        session.add(
            RefreshToken(
                user_id=operator.id,
                token_hash=hash_refresh_token(raw_refresh_token),
                expires_at=utc_now() + timedelta(days=14),
            ),
        )
        await session.commit()

    response = await app_client.patch(
        f"/api/v1/operators/{operator.id}",
        json={
            "username": "patched",
            "full_name": "Patched Operator",
            "is_active": False,
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["username"] == "patched"
    assert response.json()["full_name"] == "Patched Operator"
    assert response.json()["is_active"] is False
    async with postgres_session_factory() as session:
        token = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(raw_refresh_token),
            ),
        )
    assert token is not None
    assert token.revoked_at is not None


@pytest.mark.asyncio
async def test_patch_operator_rejects_admin_target_and_duplicate_username(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    headers = await admin_headers(app_client, postgres_session_factory)
    admin_target = await create_user(postgres_session_factory, "other-admin", UserRole.ADMIN)
    await create_user(postgres_session_factory, "taken", UserRole.OPERATOR)
    operator = await create_user(postgres_session_factory, "operator", UserRole.OPERATOR)

    admin_response = await app_client.patch(
        f"/api/v1/operators/{admin_target.id}",
        json={"full_name": "Changed"},
        headers=headers,
    )
    duplicate_response = await app_client.patch(
        f"/api/v1/operators/{operator.id}",
        json={"username": "taken"},
        headers=headers,
    )

    assert admin_response.status_code == 404
    assert admin_response.json()["error"]["code"] == "OPERATOR_NOT_FOUND"
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "USERNAME_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_reset_password_returns_temporary_password_once_and_revokes_tokens(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    headers = await admin_headers(app_client, postgres_session_factory)
    operator = await create_user(postgres_session_factory, "reset-me", UserRole.OPERATOR)
    raw_refresh_token = "operator-refresh-token"
    async with postgres_session_factory() as session:
        session.add(
            RefreshToken(
                user_id=operator.id,
                token_hash=hash_refresh_token(raw_refresh_token),
                expires_at=utc_now() + timedelta(days=14),
            ),
        )
        await session.commit()

    response = await app_client.post(
        f"/api/v1/operators/{operator.id}/reset-password",
        headers=headers,
    )

    assert response.status_code == 200
    temporary_password = response.json()["temporary_password"]
    assert len(temporary_password) == 24
    detail = await app_client.get(f"/api/v1/operators/{operator.id}", headers=headers)
    assert "temporary_password" not in detail.json()

    login_response = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "reset-me", "password": temporary_password},
    )
    assert login_response.status_code == 200
    async with postgres_session_factory() as session:
        token = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(raw_refresh_token),
            ),
        )
    assert token is not None
    assert token.revoked_at is not None


@pytest.mark.asyncio
async def test_login_history_and_stats(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    headers = await admin_headers(app_client, postgres_session_factory)
    operator = await create_user(postgres_session_factory, "history", UserRole.OPERATOR)
    async with postgres_session_factory() as session:
        session.add_all(
            [
                LoginEvent(
                    user_id=operator.id,
                    username_entered="history",
                    success=True,
                    occurred_at=utc_now() - timedelta(minutes=5),
                    ip_address="127.0.0.1",
                    user_agent="first",
                ),
                LoginEvent(
                    user_id=operator.id,
                    username_entered="history",
                    success=False,
                    failure_reason=LoginFailureReason.INVALID_CREDENTIALS,
                    occurred_at=utc_now(),
                    ip_address="127.0.0.2",
                    user_agent="second",
                ),
            ],
        )
        await session.commit()

    history_response = await app_client.get(
        f"/api/v1/operators/{operator.id}/login-history",
        headers=headers,
    )
    stats_response = await app_client.get(
        f"/api/v1/operators/{operator.id}/login-stats",
        headers=headers,
    )

    assert history_response.status_code == 200
    history = history_response.json()
    assert history["total"] == 2
    assert history["items"][0]["success"] is False
    assert history["items"][0]["failure_reason"] == "invalid_credentials"
    assert history["items"][0]["ip_address"] == "127.0.0.2"
    assert history["items"][0]["user_agent"] == "second"

    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["successful_count"] == 1
    assert stats["last_successful_login_at"] is not None
