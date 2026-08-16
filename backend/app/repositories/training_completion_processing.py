from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models import (
    SimulationEvent,
    SimulationSession,
    SimulationTimelineEventType,
    TrainingCompletionProcessing,
)


class TrainingCompletionProcessingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def discover(self, limit: int = 100) -> int:
        tracked = exists(
            select(TrainingCompletionProcessing.id).where(
                TrainingCompletionProcessing.event_id == SimulationEvent.id
            )
        )
        result = await self._session.execute(
            select(SimulationEvent)
            .join(SimulationSession, SimulationSession.id == SimulationEvent.session_id)
            .where(
                SimulationEvent.event_type == SimulationTimelineEventType.SESSION_COMPLETED,
                SimulationSession.training_scenario_id.is_not(None),
                ~tracked,
            )
            .order_by(SimulationEvent.created_at.asc(), SimulationEvent.id.asc())
            .limit(limit)
        )
        events = list(result.scalars())
        self._session.add_all(
            [
                TrainingCompletionProcessing(
                    event_id=event.id,
                    session_id=event.session_id,
                    status="pending",
                )
                for event in events
            ]
        )
        if events:
            await self._session.flush()
        return len(events)

    async def list_retryable_ids(self, max_attempts: int, limit: int = 100) -> list[UUID]:
        result = await self._session.execute(
            select(TrainingCompletionProcessing.id)
            .where(
                TrainingCompletionProcessing.status.in_(("pending", "failed")),
                TrainingCompletionProcessing.attempts < max_attempts,
            )
            .order_by(
                TrainingCompletionProcessing.updated_at.asc(),
                TrainingCompletionProcessing.id.asc(),
            )
            .limit(limit)
        )
        return list(result.scalars())

    async def get(self, processing_id: UUID) -> TrainingCompletionProcessing | None:
        result = await self._session.execute(
            select(TrainingCompletionProcessing).where(
                TrainingCompletionProcessing.id == processing_id
            )
        )
        return result.scalar_one_or_none()

    async def register_attempt(self, item: TrainingCompletionProcessing) -> None:
        item.attempts += 1
        item.status = "pending"
        item.last_error = None
        item.updated_at = utc_now()
        await self._session.flush()

    async def mark_completed(
        self,
        item: TrainingCompletionProcessing,
        result: dict[str, object],
    ) -> None:
        now = utc_now()
        item.status = "completed"
        item.last_error = None
        item.result = result
        item.processed_at = now
        item.updated_at = now
        await self._session.flush()

    async def mark_failed(self, item: TrainingCompletionProcessing, error: str) -> None:
        item.status = "failed"
        item.last_error = error[:2000]
        item.updated_at = utc_now()
        await self._session.flush()
