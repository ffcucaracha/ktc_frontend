import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.simulation.dto import SimulationState
from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.models import SimulationEvent, SimulationSession, SimulatorDefinition, User, UserRole
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


@pytest.mark.asyncio
async def test_server_side_collector_persists_snapshots_without_frontend_polling(
    postgres_session_factory: async_sessionmaker,
) -> None:
    gateway = AdvancingGateway()
    async with postgres_session_factory() as session:
        operator = User(
            username=f"telemetry-{uuid4()}",
            full_name="Telemetry Operator",
            role=UserRole.OPERATOR,
            password_hash=hash_password("secret-password"),
            is_active=True,
        )
        simulator = SimulatorDefinition(
            code=f"telemetry-{uuid4()}",
            external_id="boiler-001",
            name="Telemetry simulator",
            description="Collector test",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add_all([operator, simulator])
        await session.commit()
        created = await SimulationService(session, gateway).create_session(operator.id, simulator.id)
        session_id = created.id

    collector = SimulationTelemetryCollector(
        postgres_session_factory,
        gateway,
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
        stored_session = await session.get(SimulationSession, session_id)

    assert snapshot_count is not None and snapshot_count >= 2
    assert stored_session is not None and stored_session.last_state is not None
    revision = stored_session.last_state.get("revision")
    assert isinstance(revision, int) and revision >= 2
