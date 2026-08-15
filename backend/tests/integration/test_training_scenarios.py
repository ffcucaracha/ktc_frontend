from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.models import (
    SimulationEvent,
    SimulatorDefinition,
    TrainingScenario,
    TrainingScenarioDifficulty,
    TrainingSessionMode,
    User,
    UserRole,
)
from app.security.passwords import hash_password
from app.services.simulation import SimulationService, TrainingScenarioNotFoundError


@pytest.mark.asyncio
async def test_scenario_is_bound_to_session_and_timeline(
    postgres_session_factory: async_sessionmaker,
) -> None:
    gateway = MockSimulationGateway()
    async with postgres_session_factory() as session:
        operator = User(
            username=f"scenario-{uuid4()}",
            full_name="Scenario Operator",
            role=UserRole.OPERATOR,
            password_hash=hash_password("secret-password"),
            is_active=True,
        )
        simulator = SimulatorDefinition(
            code=f"scenario-simulator-{uuid4()}",
            external_id="boiler-001",
            name="Scenario simulator",
            description="Scenario test",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add_all([operator, simulator])
        await session.flush()
        scenario = TrainingScenario(
            code=f"scenario-{uuid4()}",
            simulator_definition_id=simulator.id,
            name="Basic startup",
            description="Test scenario",
            difficulty=TrainingScenarioDifficulty.BASIC,
            is_active=True,
            config={"version": 1},
        )
        session.add(scenario)
        await session.commit()

        created = await SimulationService(session, gateway).create_session(
            operator.id,
            simulator.id,
            training_scenario_id=scenario.id,
            mode=TrainingSessionMode.EXAM,
        )

        assert created.training_scenario_id == scenario.id
        assert created.mode == TrainingSessionMode.EXAM

        event = (
            await session.execute(
                select(SimulationEvent).where(
                    SimulationEvent.session_id == created.id,
                    SimulationEvent.event_type == "session.started",
                )
            )
        ).scalar_one()
        assert event.payload["training_scenario_id"] == str(scenario.id)
        assert event.payload["training_scenario_code"] == scenario.code
        assert event.payload["mode"] == "exam"


@pytest.mark.asyncio
async def test_rejects_scenario_from_another_simulator(
    postgres_session_factory: async_sessionmaker,
) -> None:
    gateway = MockSimulationGateway()
    async with postgres_session_factory() as session:
        operator = User(
            username=f"scenario-owner-{uuid4()}",
            full_name="Scenario Owner",
            role=UserRole.OPERATOR,
            password_hash=hash_password("secret-password"),
            is_active=True,
        )
        simulator = SimulatorDefinition(
            code=f"target-{uuid4()}",
            external_id="boiler-001",
            name="Target",
            description="",
            visualization_type="boiler-v1",
            is_active=True,
        )
        other_simulator = SimulatorDefinition(
            code=f"other-{uuid4()}",
            external_id=f"other-{uuid4()}",
            name="Other",
            description="",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add_all([operator, simulator, other_simulator])
        await session.flush()
        foreign_scenario = TrainingScenario(
            code=f"foreign-{uuid4()}",
            simulator_definition_id=other_simulator.id,
            name="Foreign",
            description="",
            difficulty=TrainingScenarioDifficulty.BASIC,
            is_active=True,
            config={},
        )
        session.add(foreign_scenario)
        await session.commit()

        with pytest.raises(TrainingScenarioNotFoundError):
            await SimulationService(session, gateway).create_session(
                operator.id,
                simulator.id,
                training_scenario_id=foreign_scenario.id,
            )
