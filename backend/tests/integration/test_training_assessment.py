from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.models import (
    OperatorErrorSource,
    OperatorErrorType,
    ScenarioExpectedAction,
    SimulatorDefinition,
    TrainingScenario,
    TrainingScenarioDifficulty,
    User,
    UserRole,
)
from app.security.passwords import hash_password
from app.services.assessment import AssessmentService
from app.services.simulation import SimulationService


@pytest.mark.asyncio
async def test_wrong_sequence_is_deterministic_and_idempotent(
    postgres_session_factory: async_sessionmaker,
) -> None:
    async with postgres_session_factory() as session:
        operator = User(
            username=f"assessment-{uuid4()}",
            full_name="Assessment Operator",
            role=UserRole.OPERATOR,
            password_hash=hash_password("secret-password"),
            is_active=True,
        )
        simulator = SimulatorDefinition(
            code=f"assessment-simulator-{uuid4()}",
            external_id="boiler-001",
            name="Assessment simulator",
            description="Assessment test",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add_all([operator, simulator])
        await session.flush()

        scenario = TrainingScenario(
            code=f"assessment-{uuid4()}",
            simulator_definition_id=simulator.id,
            name="Sequence assessment",
            description="Supply pump must be started before exhaust pump.",
            difficulty=TrainingScenarioDifficulty.BASIC,
            is_active=True,
            config={"version": 1},
        )
        session.add(scenario)
        await session.flush()
        session.add_all(
            [
                ScenarioExpectedAction(
                    scenario_id=scenario.id,
                    step_code="start-supply",
                    equipment_id="steam_supply_pump",
                    action="start",
                    payload_constraints=None,
                    condition={},
                    allowed_delay_ms=15_000,
                    severity_if_missed="warning",
                    order_index=1,
                ),
                ScenarioExpectedAction(
                    scenario_id=scenario.id,
                    step_code="start-exhaust",
                    equipment_id="steam_exhaust_pump",
                    action="start",
                    payload_constraints=None,
                    condition={},
                    allowed_delay_ms=15_000,
                    severity_if_missed="warning",
                    order_index=2,
                ),
            ]
        )
        await session.commit()

        service = SimulationService(session, MockSimulationGateway())
        simulation_session = await service.create_session(
            operator.id,
            simulator.id,
            training_scenario_id=scenario.id,
        )
        await service.send_command(
            session_id=simulation_session.id,
            operator_id=operator.id,
            command_id=uuid4(),
            equipment_id="steam_exhaust_pump",
            action="start",
            payload={},
            expected_revision=1,
        )

        first = await AssessmentService(session).assess_session(
            simulation_session.id,
            operator.id,
        )
        second = await AssessmentService(session).assess_session(
            simulation_session.id,
            operator.id,
        )

    assert first.result.score == 85.0
    assert second.result.score == 85.0
    assert first.result.error_count == 1
    assert second.result.error_count == 1
    assert [item.error_type for item in first.errors] == [OperatorErrorType.WRONG_SEQUENCE]
    assert [item.error_type for item in second.errors] == [OperatorErrorType.WRONG_SEQUENCE]
    assert all(item.source == OperatorErrorSource.RULE for item in second.errors)
