from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SimulationEventSource, SimulationTimelineEventType
from app.repositories.simulation_events import SimulationEventRepository
from app.services.training_narrative import SessionNarrative


class AIAuditService:
    """Persist reproducible AI diagnostics without storing prompts or secrets."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events = SimulationEventRepository(session)

    async def record_error(
        self,
        *,
        session_id: UUID,
        operation: str,
        error_code: str,
    ) -> None:
        await self._events.create_event(
            session_id=session_id,
            event_type=SimulationTimelineEventType.INTEGRATION_ERROR,
            source=SimulationEventSource.AI,
            payload={
                "integration": "ai",
                "operation": operation,
                "error_code": error_code,
            },
        )

    async def record_narrative(
        self,
        *,
        session_id: UUID,
        training_result_id: UUID,
        narrative: SessionNarrative,
    ) -> None:
        audit_key = f"debrief:{training_result_id}:{narrative.debrief_model}"
        recent = await self._events.list_recent_for_session(session_id, limit=200)
        if any(
            event.event_type == SimulationTimelineEventType.AI_EXPLANATION_READY
            and event.payload.get("audit_key") == audit_key
            for event in recent
        ):
            return

        source_references = [
            source
            for explanation in narrative.error_explanations
            for source in explanation.sources
        ]
        await self._events.create_event(
            session_id=session_id,
            event_type=SimulationTimelineEventType.AI_EXPLANATION_READY,
            source=SimulationEventSource.AI,
            payload={
                "audit_key": audit_key,
                "training_result_id": str(training_result_id),
                "debrief_model": narrative.debrief_model,
                "generated_by": narrative.generated_by,
                "source_references": source_references,
                "error_models": [
                    {
                        "error_id": str(item.error_id),
                        "model": item.model,
                        "source_references": item.sources,
                    }
                    for item in narrative.error_explanations
                ],
            },
        )
        if narrative.ai_error_code is not None:
            await self.record_error(
                session_id=session_id,
                operation="build_debrief",
                error_code=narrative.ai_error_code,
            )
