import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.websockets import WebSocketDisconnect

from app.api.dependencies import get_simulation_gateway
from app.core.config import get_settings
from app.db.session import get_session
from app.integrations.simulation.dto import SimulationEvent, SimulationEventType, SimulationState
from app.integrations.simulation.errors import SimulationTimeoutError
from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.main import create_app
from app.models import (
    SimulationCommand,
    SimulationCommandStatus,
    SimulationSession,
    SimulationSessionStatus,
    SimulatorDefinition,
    User,
    UserRole,
)
from app.security.passwords import hash_password
from app.security.tokens import create_access_token


class StaleStateGateway(MockSimulationGateway):
    async def get_state(self, external_session_id: str) -> SimulationState:
        state = await super().get_state(external_session_id)
        return state.model_copy(update={"revision": 1})


class RelayGateway(MockSimulationGateway):
    def __init__(self) -> None:
        super().__init__()
        self.stream_closed = False

    async def stream_events(self, external_session_id: str) -> AsyncIterator[SimulationEvent]:
        del external_session_id
        try:
            yield SimulationEvent(
                type=SimulationEventType.SESSION_READY,
                data={"status": "active"},
            )
            yield SimulationEvent(
                type=SimulationEventType.STATE_SNAPSHOT,
                data=self._initial_state()
                .model_copy(update={"revision": 2})
                .model_dump(mode="json"),
            )
        finally:
            self.stream_closed = True


async def create_user(
    session_factory: async_sessionmaker,
    username: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    async with session_factory() as session:
        user = User(
            username=username,
            full_name=f"{username} User",
            role=role,
            password_hash=hash_password("secret-password"),
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        return user


async def create_simulator(session_factory: async_sessionmaker) -> SimulatorDefinition:
    async with session_factory() as session:
        simulator = SimulatorDefinition(
            code=f"boiler-demo-{uuid4()}",
            external_id="boiler-001",
            name="Котёл с двумя насосами",  # noqa: RUF001
            description="Demo boiler",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add(simulator)
        await session.commit()
        return simulator


async def create_active_session(
    session_factory: async_sessionmaker,
    operator: User,
    simulator: SimulatorDefinition,
    last_revision: int = 1,
) -> SimulationSession:
    state = MockSimulationGateway._initial_state().model_copy(update={"revision": last_revision})
    async with session_factory() as session:
        simulation_session = SimulationSession(
            operator_id=operator.id,
            simulator_definition_id=simulator.id,
            external_session_id=f"external-{uuid4()}",
            status=SimulationSessionStatus.ACTIVE,
            last_state=state.model_dump(mode="json"),
        )
        session.add(simulation_session)
        await session.commit()
        return simulation_session


async def auth_headers(client: AsyncClient, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret-password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def build_app(session_factory: async_sessionmaker, gateway: MockSimulationGateway):
    app = create_app()

    async def override_session() -> AsyncIterator:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_simulation_gateway] = lambda: gateway
    return app


@pytest.mark.asyncio
async def test_catalog_and_session_create(
    postgres_session_factory: async_sessionmaker,
) -> None:
    operator = await create_user(postgres_session_factory, "operator", UserRole.OPERATOR)
    simulator = await create_simulator(postgres_session_factory)
    gateway = MockSimulationGateway()
    app = build_app(postgres_session_factory, gateway)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await auth_headers(client, operator.username)

        catalog = await client.get("/api/v1/simulators", headers=headers)
        assert catalog.status_code == 200
        assert catalog.json()["items"][0]["id"] == str(simulator.id)

        detail = await client.get(f"/api/v1/simulators/{simulator.id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["code"] == simulator.code

        created = await client.post(
            "/api/v1/simulation-sessions",
            json={"simulator_id": str(simulator.id)},
            headers=headers,
        )

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == SimulationSessionStatus.ACTIVE
    assert body["external_session_id"] == "mock-boiler-001"
    assert body["last_state"]["revision"] == 1


@pytest.mark.asyncio
async def test_session_ownership_and_admin_denied(
    postgres_session_factory: async_sessionmaker,
) -> None:
    owner = await create_user(postgres_session_factory, "owner", UserRole.OPERATOR)
    other = await create_user(postgres_session_factory, "other", UserRole.OPERATOR)
    admin = await create_user(postgres_session_factory, "admin", UserRole.ADMIN)
    simulator = await create_simulator(postgres_session_factory)
    simulation_session = await create_active_session(postgres_session_factory, owner, simulator)
    app = build_app(postgres_session_factory, MockSimulationGateway())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_headers = await auth_headers(client, owner.username)
        other_headers = await auth_headers(client, other.username)
        admin_headers = await auth_headers(client, admin.username)

        owned = await client.get(
            f"/api/v1/simulation-sessions/{simulation_session.id}", headers=owner_headers
        )
        foreign = await client.get(
            f"/api/v1/simulation-sessions/{simulation_session.id}", headers=other_headers
        )
        admin_response = await client.get(
            f"/api/v1/simulation-sessions/{simulation_session.id}",
            headers=admin_headers,
        )

    assert owned.status_code == 200
    assert foreign.status_code == 404
    assert admin_response.status_code == 403


@pytest.mark.asyncio
async def test_command_accepted_rejected_timeout_and_invalid_command(
    postgres_session_factory: async_sessionmaker,
) -> None:
    operator = await create_user(postgres_session_factory, "operator", UserRole.OPERATOR)
    simulator = await create_simulator(postgres_session_factory)

    async def post_command(
        gateway: MockSimulationGateway, action: str = "start"
    ) -> tuple[int, dict[str, object]]:
        simulation_session = await create_active_session(
            postgres_session_factory, operator, simulator
        )
        app = build_app(postgres_session_factory, gateway)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await auth_headers(client, operator.username)
            response = await client.post(
                f"/api/v1/simulation-sessions/{simulation_session.id}/commands",
                json={
                    "command_id": str(uuid4()),
                    "equipment_id": "steam_supply_pump",
                    "action": action,
                    "payload": {},
                    "expected_revision": 1,
                },
                headers=headers,
            )
        return response.status_code, response.json()

    accepted_status, accepted_body = await post_command(MockSimulationGateway())
    rejected_status, rejected_body = await post_command(MockSimulationGateway(reject_commands=True))
    timeout_status, timeout_body = await post_command(MockSimulationGateway(timeout=True))
    invalid_status, invalid_body = await post_command(MockSimulationGateway(), action="open")

    assert accepted_status == 200
    assert accepted_body["status"] == SimulationCommandStatus.ACCEPTED
    assert rejected_status == 200
    assert rejected_body["status"] == SimulationCommandStatus.REJECTED
    assert rejected_body["external_error_code"] == "COMMAND_REJECTED"
    assert timeout_status == 504
    assert timeout_body["error"]["code"] == SimulationTimeoutError().code.value
    assert invalid_status == 400
    assert invalid_body["error"]["code"] == "INVALID_COMMAND"

    async with postgres_session_factory() as session:
        commands = (await session.execute(select(SimulationCommand))).scalars().all()
    assert {command.status for command in commands} >= {
        SimulationCommandStatus.ACCEPTED,
        SimulationCommandStatus.REJECTED,
        SimulationCommandStatus.FAILED,
    }


@pytest.mark.asyncio
async def test_accepted_command_does_not_change_local_state_until_snapshot(
    postgres_session_factory: async_sessionmaker,
) -> None:
    operator = await create_user(postgres_session_factory, "operator", UserRole.OPERATOR)
    simulator = await create_simulator(postgres_session_factory)
    simulation_session = await create_active_session(postgres_session_factory, operator, simulator)
    app = build_app(postgres_session_factory, MockSimulationGateway())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await auth_headers(client, operator.username)
        response = await client.post(
            f"/api/v1/simulation-sessions/{simulation_session.id}/commands",
            json={
                "command_id": str(uuid4()),
                "equipment_id": "steam_supply_pump",
                "action": "start",
                "payload": {},
            },
            headers=headers,
        )

    assert response.status_code == 200
    async with postgres_session_factory() as session:
        saved_session = await session.get(SimulationSession, simulation_session.id)
    assert saved_session is not None
    assert saved_session.last_state is not None
    assert saved_session.last_state["equipment"]["steam_supply_pump"]["status"] == "stopped"


@pytest.mark.asyncio
async def test_stale_revision_and_stop_idempotency(
    postgres_session_factory: async_sessionmaker,
) -> None:
    operator = await create_user(postgres_session_factory, "operator", UserRole.OPERATOR)
    simulator = await create_simulator(postgres_session_factory)
    simulation_session = await create_active_session(
        postgres_session_factory, operator, simulator, last_revision=5
    )
    app = build_app(postgres_session_factory, StaleStateGateway())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await auth_headers(client, operator.username)

        stale = await client.get(
            f"/api/v1/simulation-sessions/{simulation_session.id}/state", headers=headers
        )
        first_stop = await client.post(
            f"/api/v1/simulation-sessions/{simulation_session.id}/stop", headers=headers
        )
        second_stop = await client.post(
            f"/api/v1/simulation-sessions/{simulation_session.id}/stop", headers=headers
        )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STALE_STATE_REVISION"
    assert first_stop.status_code == 200
    assert first_stop.json()["status"] == SimulationSessionStatus.COMPLETED
    assert second_stop.status_code == 200
    assert second_stop.json()["status"] == SimulationSessionStatus.COMPLETED


async def seed_websocket_data(database_url: str) -> tuple[UUID, UUID, UUID]:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        operator = await create_user(session_factory, "ws-operator", UserRole.OPERATOR)
        other = await create_user(session_factory, "ws-other", UserRole.OPERATOR)
        simulator = await create_simulator(session_factory)
        simulation_session = await create_active_session(session_factory, operator, simulator)
        return operator.id, other.id, simulation_session.id
    finally:
        await engine.dispose()


def build_websocket_app(database_url: str, gateway: RelayGateway):
    app = create_app()

    async def override_session() -> AsyncIterator:
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                yield session
        finally:
            await engine.dispose()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_simulation_gateway] = lambda: gateway
    return app


def test_websocket_auth_relay_and_disconnect_cleanup(migrated_database: str) -> None:
    operator_id, other_id, session_id = asyncio.run(seed_websocket_data(migrated_database))
    gateway = RelayGateway()
    app = build_websocket_app(migrated_database, gateway)
    settings = get_settings()
    operator_token = create_access_token(operator_id, settings)
    other_token = create_access_token(other_id, settings)

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/ws/v1/simulation-sessions/{session_id}?access_token={other_token}"
        ) as foreign_ws:
            with pytest.raises(WebSocketDisconnect):
                foreign_ws.receive_json()

        with client.websocket_connect(
            f"/ws/v1/simulation-sessions/{session_id}?access_token={operator_token}"
        ) as ws:
            ready_event = ws.receive_json()
            snapshot_event = ws.receive_json()

    assert ready_event["type"] == SimulationEventType.SESSION_READY
    assert snapshot_event["type"] == SimulationEventType.STATE_SNAPSHOT
    assert snapshot_event["data"]["revision"] == 2
    assert gateway.stream_closed is True
