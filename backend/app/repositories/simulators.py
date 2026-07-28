from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SimulatorDefinition

BOILER_DEMO_CODE = "boiler-demo"
BOILER_DEMO_EXTERNAL_ID = "boiler-001"
BOILER_DEMO_NAME = "Котёл с двумя насосами"  # noqa: RUF001
BOILER_DEMO_VISUALIZATION_TYPE = "boiler-v1"
BOILER_DEMO_DESCRIPTION = "Демонстрационная установка MVP: котёл и два насоса."
KTC_OIL_HEATING_CODE = "oil-heating-ktc"
KTC_OIL_HEATING_EXTERNAL_ID = "ktc-oil-heating"
KTC_OIL_HEATING_NAME = "Подогрев сырой нефти перед ЭЛОУ"
KTC_OIL_HEATING_VISUALIZATION_TYPE = "oil-heating-v1"
KTC_OIL_HEATING_DESCRIPTION = "Тренажёр блока подогрева нефти с подключением к ktc_backend."


class SimulatorDefinitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: str) -> SimulatorDefinition | None:
        result = await self._session.execute(
            select(SimulatorDefinition).where(SimulatorDefinition.code == code),
        )
        return result.scalar_one_or_none()

    async def upsert_boiler_demo(self) -> SimulatorDefinition:
        simulator = await self.get_by_code(BOILER_DEMO_CODE)
        if simulator is None:
            simulator = SimulatorDefinition(
                code=BOILER_DEMO_CODE,
                external_id=BOILER_DEMO_EXTERNAL_ID,
                name=BOILER_DEMO_NAME,
                description=BOILER_DEMO_DESCRIPTION,
                visualization_type=BOILER_DEMO_VISUALIZATION_TYPE,
                is_active=True,
            )
            self._session.add(simulator)
        else:
            simulator.external_id = BOILER_DEMO_EXTERNAL_ID
            simulator.name = BOILER_DEMO_NAME
            simulator.description = BOILER_DEMO_DESCRIPTION
            simulator.visualization_type = BOILER_DEMO_VISUALIZATION_TYPE
            simulator.is_active = True

        await self._session.flush()
        return simulator

    async def upsert_ktc_oil_heating(self) -> SimulatorDefinition:
        simulator = await self.get_by_code(KTC_OIL_HEATING_CODE)
        if simulator is None:
            simulator = SimulatorDefinition(
                code=KTC_OIL_HEATING_CODE,
                external_id=KTC_OIL_HEATING_EXTERNAL_ID,
                name=KTC_OIL_HEATING_NAME,
                description=KTC_OIL_HEATING_DESCRIPTION,
                visualization_type=KTC_OIL_HEATING_VISUALIZATION_TYPE,
                is_active=True,
            )
            self._session.add(simulator)
        else:
            simulator.external_id = KTC_OIL_HEATING_EXTERNAL_ID
            simulator.name = KTC_OIL_HEATING_NAME
            simulator.description = KTC_OIL_HEATING_DESCRIPTION
            simulator.visualization_type = KTC_OIL_HEATING_VISUALIZATION_TYPE
            simulator.is_active = True

        await self._session.flush()
        return simulator
