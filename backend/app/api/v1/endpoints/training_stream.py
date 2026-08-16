import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.api.dependencies import websocket_current_user
from app.api.errors import ApiError
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import SimulationTimelineEventType, UserRole
from app.repositories.simulation_events import SimulationEventRepository
from app.repositories.simulation_sessions import SimulationSessionRepository

ws_router = APIRouter(tags=["training-websocket"])
STREAM_EVENT_TYPES = {
    SimulationTimelineEventType.ASSESSMENT_ERROR_DETECTED,
    SimulationTimelineEventType.AI_RISK_UPDATED,
    SimulationTimelineEventType.AI_EXPLANATION_READY,
    SimulationTimelineEventType.TRAINING_RESULT_READY,
}


@ws_router.websocket("/ws/v1/simulation-sessions/{session_id}/training")
async def training_session_events(
    websocket: WebSocket,
    session_id: UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    await websocket.accept()
    try:
        user = await websocket_current_user(websocket, session, settings)
        if user.role != UserRole.OPERATOR:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        simulation_session = await SimulationSessionRepository(session).get_for_operator(
            session_id,
            user.id,
        )
        if simulation_session is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except ApiError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    sent_event_ids: set[UUID] = set()
    repository = SimulationEventRepository(session)
    try:
        while True:
            events = await repository.list_recent_for_session(session_id, limit=200)
            for event in reversed(events):
                if event.id in sent_event_ids:
                    continue
                sent_event_ids.add(event.id)
                if event.event_type not in STREAM_EVENT_TYPES:
                    continue
                await websocket.send_json(
                    {
                        "type": event.event_type,
                        "data": event.payload,
                    }
                )
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
