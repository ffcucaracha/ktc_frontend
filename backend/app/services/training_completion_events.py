from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.simulation_sessions import SimulationSessionRepository
from app.repositories.training_completion_processing import (
    TrainingCompletionProcessingRepository,
)
from app.services.assessment import AssessmentService
from app.services.training_insights import TrainingInsightsService

logger = logging.getLogger(__name__)


class TrainingCompletionEventProcessor:
    """Consume durable session.completed timeline events and run post-session analytics.

    Processing is intentionally idempotent: assessment and skill-profile rebuilds can safely run
    again. Failed items stay retryable until max_attempts is reached.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        polling_interval_seconds: float = 2.0,
        max_attempts: int = 5,
        batch_size: int = 100,
    ) -> None:
        self._session_factory = session_factory
        self._polling_interval_seconds = polling_interval_seconds
        self._max_attempts = max_attempts
        self._batch_size = batch_size
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="training-completion-events")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def process_once(self) -> int:
        async with self._session_factory() as session:
            repository = TrainingCompletionProcessingRepository(session)
            await repository.discover(limit=self._batch_size)
            await session.commit()
            processing_ids = await repository.list_retryable_ids(
                max_attempts=self._max_attempts,
                limit=self._batch_size,
            )

        processed = 0
        for processing_id in processing_ids:
            if await self._process_item(processing_id):
                processed += 1
        return processed

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.process_once()
            except Exception:
                logger.exception("Training completion event cycle failed")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._polling_interval_seconds,
                )
            except TimeoutError:
                pass

    async def _process_item(self, processing_id: UUID) -> bool:
        async with self._session_factory() as session:
            repository = TrainingCompletionProcessingRepository(session)
            item = await repository.get(processing_id)
            if item is None or item.status == "completed" or item.attempts >= self._max_attempts:
                return False
            await repository.register_attempt(item)
            session_id = item.session_id
            await session.commit()

        try:
            async with self._session_factory() as session:
                simulation_session = await SimulationSessionRepository(session).get(session_id)
                if simulation_session is None:
                    raise RuntimeError("Simulation session for completion event does not exist")
                if simulation_session.training_scenario_id is None:
                    raise RuntimeError("Completed session has no training scenario")

                outcome = await AssessmentService(session).assess_session(
                    session_id,
                    simulation_session.operator_id,
                )
                recommendations = await TrainingInsightsService(session).build_recommendations(
                    simulation_session.operator_id
                )

                repository = TrainingCompletionProcessingRepository(session)
                item = await repository.get(processing_id)
                if item is None:
                    return False
                await repository.mark_completed(
                    item,
                    {
                        "training_result_id": str(outcome.result.id),
                        "score": outcome.result.score,
                        "error_count": outcome.result.error_count,
                        "recommendations": [
                            {
                                "focus": recommendation.focus,
                                "priority": recommendation.priority,
                                "reason": recommendation.reason,
                            }
                            for recommendation in recommendations
                        ],
                    },
                )
                await session.commit()
            return True
        except Exception as exc:
            logger.exception(
                "Training completion event processing failed",
                extra={"processing_id": str(processing_id), "session_id": str(session_id)},
            )
            async with self._session_factory() as session:
                repository = TrainingCompletionProcessingRepository(session)
                item = await repository.get(processing_id)
                if item is not None:
                    await repository.mark_failed(
                        item,
                        f"{type(exc).__name__}: {exc}",
                    )
                    await session.commit()
            return False
