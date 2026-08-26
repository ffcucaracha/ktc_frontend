import asyncio
from typing import cast

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
    config: dict[str, object] | None = None,
) -> TrainingScenario:
    result = await session.execute(select(TrainingScenario).where(TrainingScenario.code == code))
    scenario = result.scalar_one_or_none()
    scenario_config = config or {"version": 1}

    if scenario is None:
        scenario = TrainingScenario(
            code=code,
            simulator_definition_id=simulator.id,
            name=name,
            description=description,
            difficulty=difficulty,
            is_active=True,
            config=scenario_config,
        )
        session.add(scenario)
        await session.flush()
    else:
        scenario.simulator_definition_id = simulator.id
        scenario.name = name
        scenario.description = description
        scenario.difficulty = difficulty
        scenario.is_active = True
        scenario.config = scenario_config

    existing_result = await session.execute(
        select(ScenarioExpectedAction).where(ScenarioExpectedAction.scenario_id == scenario.id)
    )
    existing_by_step = {item.step_code: item for item in existing_result.scalars()}
    expected_steps: set[str] = set()

    for action_data in actions:
        step_code = str(action_data["step_code"])
        expected_steps.add(step_code)
        action = existing_by_step.get(step_code)
        if action is None:
            action = ScenarioExpectedAction(scenario_id=scenario.id, step_code=step_code)
            session.add(action)

        action.equipment_id = str(action_data["equipment_id"])
        action.action = str(action_data["action"])
        action.payload_constraints = cast(
            dict[str, object] | None,
            action_data.get("payload_constraints"),
        )
        action.condition = cast(dict[str, object], action_data.get("condition", {}))
        action.allowed_delay_ms = cast(int | None, action_data.get("allowed_delay_ms"))
        action.severity_if_missed = str(action_data.get("severity_if_missed", "warning"))
        action.order_index = int(cast(int, action_data["order_index"]))

    for step_code, action in existing_by_step.items():
        if step_code not in expected_steps:
            await session.delete(action)

    await session.flush()
    return scenario


async def seed_simulators(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[SimulatorDefinition]:
    async with session_factory() as session:
        repository = SimulatorDefinitionRepository(session)
        boiler = await repository.upsert_boiler_demo()
        oil_heating = await repository.upsert_ktc_oil_heating()
        oil_heating_elou = await repository.upsert_ktc_oil_heating_elou()

        await _upsert_scenario(
            session,
            simulator=boiler,
            code="boiler-basic-startup",
            name="Базовый запуск котла",
            description="Последовательный запуск насосов демонстрационного котла.",
            difficulty=TrainingScenarioDifficulty.BASIC,
            config={"version": 1, "assessment_focus": ["sequence"]},
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
            description=(
                "Учебная последовательность открытия входного крана, запуска насосов H1A, "
                "H1B, H1C и включения дозатора ND1."
            ),
            difficulty=TrainingScenarioDifficulty.BASIC,
            config={"version": 1, "assessment_focus": ["sequence", "missed_action"]},
            actions=[
                {
                    "step_code": "open-kr1",
                    "equipment_id": "KR1",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "critical",
                    "order_index": 1,
                },
                {
                    "step_code": "start-h1a",
                    "equipment_id": "H1A",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 2,
                },
                {
                    "step_code": "start-h1b",
                    "equipment_id": "H1B",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 3,
                },
                {
                    "step_code": "start-h1c",
                    "equipment_id": "H1C",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 4,
                },
                {
                    "step_code": "start-nd1",
                    "equipment_id": "ND1",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 5,
                },
                {
                    "step_code": "set-nd1-flow",
                    "equipment_id": "ND1",
                    "action": "set",
                    "payload_constraints": {"value": {"min": 5, "max": 30}},
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 6,
                },
            ],
        )

        await _upsert_scenario(
            session,
            simulator=oil_heating,
            code="oil-heating-basic-shutdown",
            name="Учебная остановка блока подогрева нефти",
            description=(
                "Отработка последовательной остановки насосов H1C, H1B и H1A "
                "на командах, уже поддерживаемых ktc_backend."
            ),
            difficulty=TrainingScenarioDifficulty.BASIC,
            config={"version": 1, "assessment_focus": ["sequence", "missed_action"]},
            actions=[
                {
                    "step_code": "stop-h1c",
                    "equipment_id": "H1C",
                    "action": "stop",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 1,
                },
                {
                    "step_code": "stop-h1b",
                    "equipment_id": "H1B",
                    "action": "stop",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 2,
                },
                {
                    "step_code": "stop-h1a",
                    "equipment_id": "H1A",
                    "action": "stop",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 3,
                },
            ],
        )

        await _upsert_scenario(
            session,
            simulator=oil_heating,
            code="oil-heating-flow-control",
            name="Управление расходом в блоке подогрева нефти",
            description=(
                "Открытие KR1, запуск H1A и последовательная установка регуляторов FRC404, "
                "FRC405 и FRC406 в учебный диапазон 40-60%."
            ),
            difficulty=TrainingScenarioDifficulty.MEDIUM,
            config={"version": 1, "assessment_focus": ["sequence", "setpoint"]},
            actions=[
                {
                    "step_code": "flow-open-kr1",
                    "equipment_id": "KR1",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "critical",
                    "order_index": 1,
                },
                {
                    "step_code": "flow-start-h1a",
                    "equipment_id": "H1A",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 2,
                },
                {
                    "step_code": "set-frc404",
                    "equipment_id": "FRC404",
                    "action": "set",
                    "payload_constraints": {"value": {"min": 40, "max": 60}},
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 3,
                },
                {
                    "step_code": "set-frc405",
                    "equipment_id": "FRC405",
                    "action": "set",
                    "payload_constraints": {"value": {"min": 40, "max": 60}},
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 4,
                },
                {
                    "step_code": "set-frc406",
                    "equipment_id": "FRC406",
                    "action": "set",
                    "payload_constraints": {"value": {"min": 40, "max": 60}},
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 5,
                },
            ],
        )

        await _upsert_scenario(
            session,
            simulator=oil_heating,
            code="oil-heating-wrong-sequence-training",
            name="Контроль последовательности запуска",
            description=(
                "Сценарий для выявления нарушения порядка действий: ожидается запуск "
                "KR1 -> H1A -> H1B -> H1C."
            ),
            difficulty=TrainingScenarioDifficulty.MEDIUM,
            config={"version": 1, "assessment_focus": ["wrong_sequence"]},
            actions=[
                {
                    "step_code": "sequence-open-kr1",
                    "equipment_id": "KR1",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "critical",
                    "order_index": 1,
                },
                {
                    "step_code": "sequence-start-h1a",
                    "equipment_id": "H1A",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 2,
                },
                {
                    "step_code": "sequence-start-h1b",
                    "equipment_id": "H1B",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 3,
                },
                {
                    "step_code": "sequence-start-h1c",
                    "equipment_id": "H1C",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 4,
                },
            ],
        )

        await _upsert_scenario(
            session,
            simulator=oil_heating,
            code="oil-heating-reaction-time-training",
            name="Тренировка времени реакции",
            description=(
                "Последовательный запуск H1A, H1B и H1C при малом допустимом времени "
                "реакции для последующей классификации LATE_ACTION."
            ),
            difficulty=TrainingScenarioDifficulty.MEDIUM,
            config={"version": 1, "assessment_focus": ["reaction_time", "late_action"]},
            actions=[
                {
                    "step_code": "reaction-open-kr1",
                    "equipment_id": "KR1",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 5_000,
                    "severity_if_missed": "critical",
                    "order_index": 1,
                },
                {
                    "step_code": "reaction-start-h1a",
                    "equipment_id": "H1A",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 5_000,
                    "severity_if_missed": "warning",
                    "order_index": 2,
                },
                {
                    "step_code": "reaction-start-h1b",
                    "equipment_id": "H1B",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 5_000,
                    "severity_if_missed": "warning",
                    "order_index": 3,
                },
                {
                    "step_code": "reaction-start-h1c",
                    "equipment_id": "H1C",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 5_000,
                    "severity_if_missed": "warning",
                    "order_index": 4,
                },
            ],
        )

        await _upsert_scenario(
            session,
            simulator=oil_heating_elou,
            code="oil-heating-elou-integrated-startup",
            name="Комплексный запуск подогрева и ЭЛОУ",
            description=(
                "Запуск подогрева нефти, вывод потока на KR6 и первичный запуск блока ЭЛОУ."
            ),
            difficulty=TrainingScenarioDifficulty.ADVANCED,
            config={"version": 1, "assessment_focus": ["sequence", "setpoint", "missed_action"]},
            actions=[
                {
                    "step_code": "combined-open-kr1",
                    "equipment_id": "KR1",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "critical",
                    "order_index": 1,
                },
                {
                    "step_code": "combined-start-h1a",
                    "equipment_id": "H1A",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 2,
                },
                {
                    "step_code": "combined-start-nd1",
                    "equipment_id": "ND1",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 3,
                },
                {
                    "step_code": "combined-set-nd1",
                    "equipment_id": "ND1",
                    "action": "set",
                    "payload_constraints": {"value": {"min": 5, "max": 30}},
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 4,
                },
                {
                    "step_code": "combined-open-kr2",
                    "equipment_id": "KR2",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 5,
                },
                {
                    "step_code": "combined-open-kr3",
                    "equipment_id": "KR3",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 6,
                },
                {
                    "step_code": "combined-open-kr4",
                    "equipment_id": "KR4",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 7,
                },
                {
                    "step_code": "combined-set-frc404",
                    "equipment_id": "FRC404",
                    "action": "set",
                    "payload_constraints": {"value": {"min": 40, "max": 80}},
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 8,
                },
                {
                    "step_code": "combined-open-kr6",
                    "equipment_id": "KR6",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "critical",
                    "order_index": 9,
                },
                {
                    "step_code": "combined-set-frc407",
                    "equipment_id": "FRC407",
                    "action": "set",
                    "payload_constraints": {"value": {"min": 40, "max": 100}},
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 10,
                },
                {
                    "step_code": "combined-start-nd2",
                    "equipment_id": "ND2",
                    "action": "start",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 11,
                },
                {
                    "step_code": "combined-set-nd2",
                    "equipment_id": "ND2",
                    "action": "set",
                    "payload_constraints": {"value": {"min": 40, "max": 50}},
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 12,
                },
                {
                    "step_code": "combined-set-water",
                    "equipment_id": "FRC408",
                    "action": "set",
                    "payload_constraints": {"value": {"min": 5, "max": 10}},
                    "condition": {},
                    "allowed_delay_ms": 15_000,
                    "severity_if_missed": "warning",
                    "order_index": 13,
                },
            ],
        )

        await _upsert_scenario(
            session,
            simulator=oil_heating_elou,
            code="oil-heating-elou-drainage-control",
            name="Контроль электродегидратора и слива воды",
            description=(
                "Отработка подачи напряжения на Э-1, слива через KR7 и разгрузки PO-1 через KR8."
            ),
            difficulty=TrainingScenarioDifficulty.ADVANCED,
            config={"version": 1, "assessment_focus": ["sequence", "wrong_action"]},
            actions=[
                {
                    "step_code": "combined-apply-e1-voltage",
                    "equipment_id": "E1",
                    "action": "apply_voltage",
                    "condition": {"E1_level": {"min": 30}},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "critical",
                    "order_index": 1,
                },
                {
                    "step_code": "combined-open-kr7",
                    "equipment_id": "KR7",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 2,
                },
                {
                    "step_code": "combined-open-kr8",
                    "equipment_id": "KR8",
                    "action": "open",
                    "condition": {},
                    "allowed_delay_ms": 20_000,
                    "severity_if_missed": "warning",
                    "order_index": 3,
                },
            ],
        )

        await session.commit()
        return [boiler, oil_heating, oil_heating_elou]


async def run() -> None:
    simulators = await seed_simulators(AsyncSessionLocal)
    simulator_codes = ", ".join(simulator.code for simulator in simulators)
    print(f"Simulators and scenarios seeded: {simulator_codes}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
