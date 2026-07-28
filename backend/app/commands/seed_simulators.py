import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import AsyncSessionLocal
from app.models import SimulatorDefinition
from app.repositories.simulators import SimulatorDefinitionRepository


async def seed_simulators(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[SimulatorDefinition]:
    async with session_factory() as session:
        repository = SimulatorDefinitionRepository(session)
        simulators = [
            await repository.upsert_boiler_demo(),
            await repository.upsert_ktc_oil_heating(),
        ]
        await session.commit()
        return simulators


async def run() -> None:
    simulators = await seed_simulators(AsyncSessionLocal)
    print(f"Simulators seeded: {', '.join(simulator.code for simulator in simulators)}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
