from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SimulationEvent, SimulationEventSource, SimulationTimelineEventType


class SimulationEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_event(
        self,
        *,
        session_id: UUID,
        event_type: str,
        source: str,
        payload: dict[str, object],
        revision: int | None = None,
        simulation_time_ms: int | None = None,
    ) -> SimulationEvent:
        event = SimulationEvent(
            session_id=session_id,
            event_type=event_type,
            source=source,
            revision=revision,
            simulation_time_ms=simulation_time_ms,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def create_state_snapshot(
        self,
        *,
        session_id: UUID,
        state: dict[str, object],
    ) -> SimulationEvent | None:
        revision = state.get("revision")
        if not isinstance(revision, int):
            raise ValueError("State snapshot must contain integer revision")

        existing = await self._session.execute(
            select(SimulationEvent.id).where(
                SimulationEvent.session_id == session_id,
                SimulationEvent.event_type == SimulationTimelineEventType.STATE_SNAPSHOT,
                SimulationEvent.revision == revision,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return None

        simulation_time_ms = state.get("simulation_time_ms")
        return await self.create_event(
            session_id=session_id,
            event_type=SimulationTimelineEventType.STATE_SNAPSHOT,
            source=SimulationEventSource.SIMULATION,
            revision=revision,
            simulation_time_ms=simulation_time_ms if isinstance(simulation_time_ms, int) else None,
            payload=state,
        )

    async def create_operator_command_event(
        self,
        *,
        session_id: UUID,
        command_id: UUID,
        equipment_id: str,
        action: str,
        payload: dict[str, object],
        expected_revision: int | None,
        simulation_time_ms: int | None = None,
    ) -> SimulationEvent:
        return await self.create_event(
            session_id=session_id,
            event_type=SimulationTimelineEventType.OPERATOR_COMMAND,
            source=SimulationEventSource.OPERATOR,
            revision=expected_revision,
            simulation_time_ms=simulation_time_ms,
            payload={
                "command_id": str(command_id),
                "equipment_id": equipment_id,
                "action": action,
                "payload": payload,
                "expected_revision": expected_revision,
            },
        )

    async def list_for_session(self, session_id: UUID) -> list[SimulationEvent]:
        result = await self._session.execute(
            select(SimulationEvent)
            .where(SimulationEvent.session_id == session_id)
            .order_by(SimulationEvent.created_at.asc(), SimulationEvent.id.asc())
        )
        return list(result.scalars())

    async def list_recent_for_session(
        self,
        session_id: UUID,
        limit: int = 100,
    ) -> list[SimulationEvent]:
        result = await self._session.execute(
            select(SimulationEvent)
            .where(SimulationEvent.session_id == session_id)
            .order_by(SimulationEvent.created_at.desc(), SimulationEvent.id.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def list_between_simulation_times(
        self,
        session_id: UUID,
        start_ms: int,
        end_ms: int,
    ) -> list[SimulationEvent]:
        result = await self._session.execute(
            select(SimulationEvent)
            .where(
                SimulationEvent.session_id == session_id,
                SimulationEvent.simulation_time_ms >= start_ms,
                SimulationEvent.simulation_time_ms <= end_ms,
            )
            .order_by(SimulationEvent.simulation_time_ms.asc(), SimulationEvent.created_at.asc())
        )
        return list(result.scalars())
