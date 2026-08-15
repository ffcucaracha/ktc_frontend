import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import AsyncSessionLocal
from app.models import (
    ScenarioExpectedAction,
    SimulatorDefinition,
    TrainingScenario,
    TrainingScenarioDifficulty,
)
from app.repositories.simulators import SimulatorDefinitionRepository


async def _upsert_scenario(
    session: AsyncSession,
    *,
    simulator: SimulatorDefinition,
    code: str,
    name: str,
    description: str,
    difficulty: TrainingScenarioDifficulty,
    actions: list[dict[str, object]],
) -> TrainingScenario:
    result = await session.execute(select(TrainingScenario).where(TrainingScenario.code == code))
    scenario = result.scalar_one_or_none()
    if scenario is None:
        scenario = TrainingScenario(
            code=code,
            simulator_definition_id=simulator.id,
            name=name,
            description=description,
            difficulty=difficulty,
            is_active=True,
            config={"version": 1},
        )
        session.add(scenario)
        await session.flush()
    else:
        scenario.simulator_definition_id = simulator.id
        scenario.name = name
        scenario.description = description
        scenario.difficulty = difficulty
        scenario.is_active = True

    existing = await session.execute(
        select(ScenarioExpectedAction.step_code).where(
            ScenarioExpectedAction.scenario_id == scenario.id
        )
    )
    existing_steps = set(existing.scalars())
    for action in actions:
        step_code = str(action["step_code"])
        if step_code in existing_steps:
            continue
        session.add(
            ScenarioExpectedAction(
                scenario_id=scenario.id,
                step_code=step_code,
                equipment_id=str(action["equipment_id"]),
                action=str(action["action"]),
                payload_constraints=action.get("payload_constraints"),
                condition=action.get("condition", {}),
                allowed_delay_ms=action.get("allowed_delay_ms"),
                severity_if_missed=str(action.get("severity_if_missed", "warning")),
                order_index=int(action["order_index"]),
            )
        )
    return scenario


async def seed_simulators(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[SimulatorDefinition]:
    async with session_factory() as session:
        repository = SimulatorDefinitionRepository(session)
        boiler = await repository.upsert_boiler_demo()
        oil_heating = await repository.upsert_ktc_oil_heating()

        await _upsert_scenario(
            session,
            simulator=boiler,
            code="boiler-basic-startup",
            name="Базовый запуск котла",
            description="Последовательный запуск насосов демонстрационного котла.",
            difficulty=TrainingScenarioDifficulty.BASIC,
            actions=[
                {
                    "step_code": "start-steam-supply",
                    "equipment_id": "steam_supply_pump",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 1,
                },
                {
                    "step_code": "start-steam-exhaust",
                    "equipment_id": "steam_exhaust_pump",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 2,
                },
            ],
        )
        await _upsert_scenario(
            session,
            simulator=oil_heating,
            code="oil-heating-basic-startup",
            name="Базовый запуск блока подогрева нефти",
            description="Учебная последовательность запуска насосов H1A, H1B и H1V.",
            difficulty=TrainingScenarioDifficulty.BASIC,
            actions=[
                {
                    "step_code": "start-h1a",
                    "equipment_id": "H1A",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 1,
                },
                {
                    "step_code": "start-h1b",
                    "equipment_id": "H1B",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 2,
                },
                {
                    "step_code": "start-h1v",
                    "equipment_id": "H1V",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 3,
                },
            ],
        )

        await session.commit()
        return [boiler, oil_heating]


async def run() -> None:
    simulators = await seed_simulators(AsyncSessionLocal)
    print(f"Simulators and scenarios seeded: {', '.join(simulator.code for simulator in simulators)}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
