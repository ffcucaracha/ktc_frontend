from __future__ import annotations

from collections import Counter
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ai.base import AIGateway
from app.integrations.ai.dto import (
    OperatorProfile,
    RecentAction,
    RiskPrediction,
    RiskPredictionRequest,
    TelemetryPoint,
)
from app.models import (
    OperatorErrorType,
    SimulationEvent,
    SimulationEventSource,
    SimulationSessionStatus,
    SimulationTimelineEventType,
    TrainingScenario,
)
from app.repositories.assessment import AssessmentRepository
from app.repositories.simulation_events import SimulationEventRepository
from app.repositories.simulation_sessions import SimulationSessionRepository

WINDOW_MS = 10_000
RECENT_EVENT_LIMIT = 200
FEATURE_VERSION = "risk-features-v1"


class RealtimeAIService:
    """Build live ML requests from authoritative timeline data and persist predictions.

    The service never changes process state. Predictions are appended to the training timeline as
    analytical events and can therefore be replayed, hidden in exam mode, or streamed to the UI.
    """

    def __init__(self, session: AsyncSession, gateway: AIGateway) -> None:
        self._session = session
        self._gateway = gateway
        self._sessions = SimulationSessionRepository(session)
        self._events = SimulationEventRepository(session)
        self._assessment = AssessmentRepository(session)

    async def predict_and_record(
        self,
        session_id: UUID,
        operator_id: UUID,
    ) -> RiskPrediction | None:
        simulation_session = await self._sessions.get_for_operator(session_id, operator_id)
        if simulation_session is None:
            return None
        if simulation_session.status != SimulationSessionStatus.ACTIVE:
            return None
        if simulation_session.training_scenario_id is None:
            return None

        scenario = await self._session.get(TrainingScenario, simulation_session.training_scenario_id)
        if scenario is None:
            return None

        timeline = list(
            reversed(
                await self._events.list_recent_for_session(
                    session_id,
                    limit=RECENT_EVENT_LIMIT,
                )
            )
        )
        snapshots = [
            event
            for event in timeline
            if event.event_type == SimulationTimelineEventType.STATE_SNAPSHOT
            and event.simulation_time_ms is not None
        ]
        if not snapshots:
            return None

        latest = snapshots[-1]
        if any(
            event.event_type == SimulationTimelineEventType.AI_RISK_UPDATED
            and event.revision == latest.revision
            for event in timeline
        ):
            return None

        latest_time_ms = latest.simulation_time_ms
        if latest_time_ms is None:
            return None

        window = [
            point
            for event in snapshots
            if latest_time_ms - WINDOW_MS <= (event.simulation_time_ms or 0) <= latest_time_ms
            if (point := _telemetry_point(event)) is not None
        ]
        if not window:
            return None

        recent_actions = [
            action
            for event in timeline
            if event.event_type == SimulationTimelineEventType.OPERATOR_COMMAND
            and event.simulation_time_ms is not None
            and event.simulation_time_ms <= latest_time_ms
            if (action := _recent_action(event)) is not None
        ]

        historical_errors = [
            error
            for error in await self._assessment.list_errors_for_operator(operator_id)
            if error.session_id != session_id
        ]
        previous_errors = Counter(_error_type_value(error.error_type) for error in historical_errors)

        prediction = await self._gateway.predict_risk(
            RiskPredictionRequest(
                session_id=session_id,
                scenario_code=scenario.code,
                operator_profile=OperatorProfile(previous_errors=dict(previous_errors)),
                window=window,
                recent_actions=recent_actions,
            )
        )
        payload = prediction.model_dump(mode="json")
        payload["feature_version"] = FEATURE_VERSION
        await self._events.create_event(
            session_id=session_id,
            event_type=SimulationTimelineEventType.AI_RISK_UPDATED,
            source=SimulationEventSource.AI,
            revision=latest.revision,
            simulation_time_ms=latest_time_ms,
            payload=payload,
        )
        await self._session.commit()
        return prediction


def _error_type_value(error_type: OperatorErrorType | str) -> str:
    return error_type.value if isinstance(error_type, OperatorErrorType) else str(error_type)


def _telemetry_point(event: SimulationEvent) -> TelemetryPoint | None:
    payload = event.payload
    revision = payload.get("revision", event.revision)
    simulation_time_ms = payload.get("simulation_time_ms", event.simulation_time_ms)
    if not isinstance(revision, int) or not isinstance(simulation_time_ms, int):
        return None

    process = payload.get("process")
    process_map = process if isinstance(process, dict) else {}
    sensors = _numeric_mapping(process_map.get("sensors"))
    pumps = _bool_mapping(process_map.get("pumps"))
    regulators = _numeric_mapping(process_map.get("regulators"))
    alarms_value = payload.get("alarms")
    alarms = [item for item in alarms_value if isinstance(item, dict)] if isinstance(alarms_value, list) else []

    return TelemetryPoint(
        simulation_time_ms=simulation_time_ms,
        revision=revision,
        sensors=sensors,
        pumps=pumps,
        regulators=regulators,
        alarms=alarms,
    )


def _recent_action(event: SimulationEvent) -> RecentAction | None:
    equipment_id = event.payload.get("equipment_id")
    action = event.payload.get("action")
    payload = event.payload.get("payload", {})
    if not isinstance(equipment_id, str) or not isinstance(action, str):
        return None
    return RecentAction(
        simulation_time_ms=event.simulation_time_ms,
        equipment_id=equipment_id,
        action=action,
        payload=payload if isinstance(payload, dict) else {},
    )


def _numeric_mapping(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, (int, float)) and not isinstance(item, bool):
            result[key] = float(item)
    return result


def _bool_mapping(value: object) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if isinstance(key, str) and isinstance(item, bool)}
