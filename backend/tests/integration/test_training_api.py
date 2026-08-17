from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.models import (
    SimulatorDefinition,
    TrainingScenario,
    TrainingScenarioDifficulty,
    TrainingSessionMode,
    User,
    UserRole,
)
from app.security.passwords import hash_password
from app.services.simulation import SimulationService


async def _create_operator(
    session_factory: async_sessionmaker,
    *,
    username: str,
    password: str,
) -> User:
    async with session_factory() as session:
        operator = User(
            username=username,
            full_name=f"{username} User",
            role=UserRole.OPERATOR,
            password_hash=hash_password(password),
            is_active=True,
        )
        session.add(operator)
        await session.commit()
        return operator


async def _login(client: AsyncClient, username: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert isinstance(token, str)
    return token


@pytest.mark.asyncio
async def test_operator_cannot_read_foreign_timeline_and_exam_hides_debrief(
    app_client: AsyncClient,
    postgres_session_factory: async_sessionmaker,
) -> None:
    suffix = str(uuid4())
    owner_password = "owner-secret"
    other_password = "other-secret"
    owner = await _create_operator(
        postgres_session_factory,
        username=f"owner-{suffix}",
        password=owner_password,
    )
    other = await _create_operator(
        postgres_session_factory,
        username=f"other-{suffix}",
        password=other_password,
    )

    async with postgres_session_factory() as session:
        simulator = SimulatorDefinition(
            code=f"exam-simulator-{suffix}",
            external_id="boiler-001",
            name="Exam simulator",
            description="Exam access test",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add(simulator)
        await session.flush()
        scenario = TrainingScenario(
            code=f"exam-scenario-{suffix}",
            simulator_definition_id=simulator.id,
            name="Exam scenario",
            description="Exam access test",
            difficulty=TrainingScenarioDifficulty.BASIC,
            is_active=True,
            config={"version": 1},
        )
        session.add(scenario)
        await session.commit()

        service = SimulationService(session, MockSimulationGateway())
        simulation_session = await service.create_session(
            owner.id,
            simulator.id,
            training_scenario_id=scenario.id,
            mode=TrainingSessionMode.EXAM,
        )

        owner_token = await _login(app_client, owner.username, owner_password)
        other_token = await _login(app_client, other.username, other_password)
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        other_headers = {"Authorization": f"Bearer {other_token}"}

        owner_timeline = await app_client.get(
            f"/api/v1/simulation-sessions/{simulation_session.id}/timeline",
            headers=owner_headers,
        )
        foreign_timeline = await app_client.get(
            f"/api/v1/simulation-sessions/{simulation_session.id}/timeline",
            headers=other_headers,
        )
        active_exam_debrief = await app_client.get(
            f"/api/v1/simulation-sessions/{simulation_session.id}/debrief",
            headers=owner_headers,
        )

        assert owner_timeline.status_code == 200
        assert foreign_timeline.status_code == 404
        assert foreign_timeline.json()["error"]["code"] == "SESSION_NOT_FOUND"
        assert active_exam_debrief.status_code == 409
        assert active_exam_debrief.json()["error"]["code"] == "EXAM_HINTS_UNAVAILABLE"

        await service.stop_session(simulation_session.id, owner.id)

    completed_exam_debrief = await app_client.get(
        f"/api/v1/simulation-sessions/{simulation_session.id}/debrief",
        headers=owner_headers,
    )
    assert completed_exam_debrief.status_code == 200
    assert completed_exam_debrief.json()["status"] == "final"
