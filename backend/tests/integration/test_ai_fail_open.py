import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.ai.errors import AIIntegrationError, AIIntegrationErrorCode
from app.integrations.simulation.dto import SimulationState
from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.models import (
    SimulationEvent,
    SimulationSession,
    SimulationSessionStatus,
    SimulatorDefinition,
    TrainingScenario,
    TrainingScenarioDifficulty,
    User,
    UserRole,
)
from app.security.passwords import hash_password
from app.services.simulation import SimulationService
from app.services.simulation_telemetry import SimulationTelemetryCollector


class AdvancingGateway(MockSimulationGateway):
    async def get_state(self, external_session_id: str) -> SimulationState:
        state = await super().get_state(external_session_id)
        next_state = state.model_copy(
            update={
                "revision": state.revision + 1,
                "simulation_time_ms": state.simulation_time_ms + 1_000,
            }
        )
        self._states[external_session_id] = next_state
        return next_state


class TimeoutAIGateway:
    async def predict_risk(self, request):
        del request
        raise AIIntegrationError(
            AIIntegrationErrorCode.AI_TIMEOUT,
            "test timeout",
        )


@pytest.mark.asyncio
async def test_ai_timeout_does_not_stop_simulation_telemetry(
    postgres_session_factory: async_sessionmaker,
) -> None:
    simulation_gateway = AdvancingGateway()
    async with postgres_session_factory() as session:
        operator = User(
            username=f"ai-fail-open-{uuid4()}",
            full_name="AI Fail Open Operator",
            role=UserRole.OPERATOR,
            password_hash=hash_password("secret-password"),
            is_active=True,
        )
        simulator = SimulatorDefinition(
            code=f"ai-fail-open-{uuid4()}",
            external_id="boiler-001",
            name="AI fail-open simulator",
            description="AI timeout test",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add_all([operator, simulator])
        await session.flush()
        scenario = TrainingScenario(
            code=f"ai-fail-open-scenario-{uuid4()}",
            simulator_definition_id=simulator.id,
            name="AI fail-open scenario",
            description="AI timeout test",
            difficulty=TrainingScenarioDifficulty.BASIC,
            is_active=True,
            config={"version": 1},
        )
        session.add(scenario)
        await session.commit()

        created = await SimulationService(session, simulation_gateway).create_session(
            operator.id,
            simulator.id,
            training_scenario_id=scenario.id,
        )
        session_id = created.id

    collector = SimulationTelemetryCollector(
        postgres_session_factory,
        simulation_gateway,
        ai_gateway=TimeoutAIGateway(),  # type: ignore[arg-type]
        polling_interval_seconds=0.01,
        discovery_interval_seconds=0.01,
    )
    await collector.start()
    await asyncio.sleep(0.08)
    await collector.stop()

    async with postgres_session_factory() as session:
        snapshot_count = await session.scalar(
            select(func.count(SimulationEvent.id)).where(
                SimulationEvent.session_id == session_id,
                SimulationEvent.event_type == "state.snapshot",
            )
        )
        ai_error_count = await session.scalar(
            select(func.count(SimulationEvent.id)).where(
                SimulationEvent.session_id == session_id,
                SimulationEvent.event_type == "integration.error",
                SimulationEvent.source == "ai",
            )
        )
        stored_session = await session.get(SimulationSession, session_id)

    assert snapshot_count is not None and snapshot_count >= 2
    assert ai_error_count is not None and ai_error_count >= 1
    assert stored_session is not None
    assert stored_session.status == SimulationSessionStatus.ACTIVE
