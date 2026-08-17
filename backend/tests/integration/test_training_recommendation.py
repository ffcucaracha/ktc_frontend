import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commands.seed_simulators import seed_simulators
from app.repositories.simulators import KTC_OIL_HEATING_CODE, SimulatorDefinitionRepository
from app.services.training_recommendation import TrainingScenarioSelector


@pytest.mark.asyncio
async def test_selector_maps_training_focus_to_active_oil_heating_scenario(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await seed_simulators(postgres_session_factory)

    async with postgres_session_factory() as session:
        simulator = await SimulatorDefinitionRepository(session).get_by_code(KTC_OIL_HEATING_CODE)
        assert simulator is not None

        selector = TrainingScenarioSelector(session)
        sequence = await selector.select_for_focus(
            simulator_id=simulator.id,
            focus="procedure_sequence",
        )
        reaction = await selector.select_for_focus(
            simulator_id=simulator.id,
            focus="reaction_speed",
        )
        regulation = await selector.select_for_focus(
            simulator_id=simulator.id,
            focus="regulation",
        )
        baseline = await selector.select_for_focus(
            simulator_id=simulator.id,
            focus="baseline",
        )

    assert sequence is not None
    assert sequence.code == "oil-heating-wrong-sequence-training"
    assert reaction is not None
    assert reaction.code == "oil-heating-reaction-time-training"
    assert regulation is not None
    assert regulation.code == "oil-heating-flow-control"
    assert baseline is not None
    assert baseline.code == "oil-heating-basic-startup"
