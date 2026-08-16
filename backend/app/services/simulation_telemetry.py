import asyncio
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.ai.base import AIGateway
from app.integrations.ai.errors import AIIntegrationError
from app.integrations.simulation.base import SimulationGateway
from app.integrations.simulation.errors import SimulationIntegrationError
from app.models import SimulationSession
from app.repositories.simulation_sessions import SimulationSessionRepository
from app.services.realtime_ai import RealtimeAIService
from app.services.simulation import (
    InvalidSessionOperationError,
    SimulationService,
    SimulationSessionNotFoundError,
    StaleStateRevisionError,
)

logger = logging.getLogger(__name__)
SleepFunc = Callable[[float], Awaitable[None]]


class SimulationTelemetryCollector:
    """Collect simulation state on the backend while sessions are active.

    MVP implementation: one asyncio task per active session in the FastAPI process.
    For horizontal scaling this collector should be moved to a dedicated worker/task queue
    so that exactly one worker owns each simulation session.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        gateway: SimulationGateway,
        *,
        ai_gateway: AIGateway | None = None,
        polling_interval_seconds: float = 2.0,
        discovery_interval_seconds: float = 1.0,
        sleep: SleepFunc = asyncio.sleep,
    ) -> None:
        self._session_factory = session_factory
        self._gateway = gateway
        self._ai_gateway = ai_gateway
        self._polling_interval_seconds = polling_interval_seconds
        self._discovery_interval_seconds = discovery_interval_seconds
        self._sleep = sleep
        self._supervisor_task: asyncio.Task[None] | None = None
        self._session_tasks: dict[UUID, asyncio.Task[None]] = {}

    @property
    def is_running(self) -> bool:
        return self._supervisor_task is not None and not self._supervisor_task.done()

    async def start(self) -> None:
        if self.is_running:
            return
        self._supervisor_task = asyncio.create_task(
            self._supervise(),
            name="simulation-telemetry-supervisor",
        )

    async def stop(self) -> None:
        supervisor = self._supervisor_task
        self._supervisor_task = None
        if supervisor is not None:
            supervisor.cancel()
            await asyncio.gather(supervisor, return_exceptions=True)
        await self._cancel_all_session_tasks()

    async def _supervise(self) -> None:
        try:
            while True:
                active_sessions = await self._load_active_sessions()
                active_ids = {item.id for item in active_sessions}

                for simulation_session in active_sessions:
                    if simulation_session.external_session_id is None:
                        continue
                    task = self._session_tasks.get(simulation_session.id)
                    if task is None or task.done():
                        self._start_session_task(simulation_session)

                for session_id, task in list(self._session_tasks.items()):
                    if session_id not in active_ids:
                        task.cancel()
                        self._session_tasks.pop(session_id, None)

                await self._sleep(self._discovery_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Simulation telemetry supervisor failed")
            raise
        finally:
            await self._cancel_all_session_tasks()

    async def _load_active_sessions(self) -> list[SimulationSession]:
        async with self._session_factory() as session:
            return await SimulationSessionRepository(session).list_active()

    def _start_session_task(self, simulation_session: SimulationSession) -> None:
        task = asyncio.create_task(
            self._collect_session(simulation_session.id, simulation_session.operator_id),
            name=f"simulation-telemetry-{simulation_session.id}",
        )
        self._session_tasks[simulation_session.id] = task
        task.add_done_callback(
            lambda completed, session_id=simulation_session.id: self._drop_finished_task(
                session_id, completed
            )
        )

    def _drop_finished_task(self, session_id: UUID, completed: asyncio.Task[None]) -> None:
        if self._session_tasks.get(session_id) is completed:
            self._session_tasks.pop(session_id, None)
        if completed.cancelled():
            return
        error = completed.exception()
        if error is not None:
            logger.error(
                "Simulation telemetry task failed",
                extra={"simulation_session_id": str(session_id)},
                exc_info=(type(error), error, error.__traceback__),
            )

    async def _collect_session(self, session_id: UUID, operator_id: UUID) -> None:
        while True:
            try:
                async with self._session_factory() as session:
                    await SimulationService(session, self._gateway).get_state(session_id, operator_id)
                    if self._ai_gateway is not None:
                        try:
                            await RealtimeAIService(session, self._ai_gateway).predict_and_record(
                                session_id,
                                operator_id,
                            )
                        except AIIntegrationError as exc:
                            logger.warning(
                                "AI risk prediction failed: %s",
                                exc,
                                extra={"simulation_session_id": str(session_id)},
                            )
            except (SimulationSessionNotFoundError, InvalidSessionOperationError):
                return
            except StaleStateRevisionError:
                # Another request/event may already have applied a newer authoritative state.
                pass
            except SimulationIntegrationError as exc:
                logger.warning(
                    "Simulation telemetry poll failed: %s",
                    exc,
                    extra={"simulation_session_id": str(session_id)},
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Unexpected simulation telemetry error",
                    extra={"simulation_session_id": str(session_id)},
                )

            await self._sleep(self._polling_interval_seconds)

    async def _cancel_all_session_tasks(self) -> None:
        tasks = list(self._session_tasks.values())
        self._session_tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
