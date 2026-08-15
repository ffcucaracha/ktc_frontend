from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models import (
    OperatorErrorType,
    ScenarioExpectedAction,
    SimulationEvent,
    SimulationEventSource,
    SimulationTimelineEventType,
)
from app.services.assessment import AssessmentService


def _event(
    *,
    equipment_id: str,
    action: str,
    offset_ms: int,
    payload: dict[str, object] | None = None,
) -> SimulationEvent:
    started = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    return SimulationEvent(
        id=uuid4(),
        session_id=uuid4(),
        event_type=SimulationTimelineEventType.OPERATOR_COMMAND,
        source=SimulationEventSource.OPERATOR,
        simulation_time_ms=offset_ms,
        payload={
            "equipment_id": equipment_id,
            "action": action,
            "payload": payload or {},
        },
        created_at=started + timedelta(milliseconds=offset_ms),
    )


def _step(order_index: int, equipment_id: str, *, allowed_delay_ms: int = 5_000) -> ScenarioExpectedAction:
    return ScenarioExpectedAction(
        id=uuid4(),
        scenario_id=uuid4(),
        step_code=f"step-{order_index}",
        equipment_id=equipment_id,
        action="start",
        condition={},
        allowed_delay_ms=allowed_delay_ms,
        severity_if_missed="warning",
        order_index=order_index,
    )


def test_detects_wrong_sequence_late_action_and_missed_action() -> None:
    service = AssessmentService.__new__(AssessmentService)
    session_id = uuid4()
    started_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    session_started = SimulationEvent(
        id=uuid4(),
        session_id=session_id,
        event_type=SimulationTimelineEventType.SESSION_STARTED,
        source=SimulationEventSource.SYSTEM,
        simulation_time_ms=0,
        payload={},
        created_at=started_at,
    )
    steps = [_step(1, "H1A"), _step(2, "H1B"), _step(3, "H1V")]
    events = [
        _event(equipment_id="H1B", action="start", offset_ms=1_000),
        _event(equipment_id="H1A", action="start", offset_ms=7_000),
        _event(equipment_id="H1B", action="start", offset_ms=8_000),
    ]
    for event in events:
        event.session_id = session_id
        event.created_at = started_at + timedelta(milliseconds=event.simulation_time_ms or 0)

    errors, matched_steps, delays = service._evaluate(
        session_id=session_id,
        expected_actions=steps,
        operator_events=events,
        session_started=session_started,
        is_final=True,
    )

    assert matched_steps == 2
    assert delays == [7_000, 1_000]
    assert [item.error_type for item in errors] == [
        OperatorErrorType.WRONG_SEQUENCE,
        OperatorErrorType.LATE_ACTION,
        OperatorErrorType.MISSED_ACTION,
    ]


def test_payload_constraint_violation_is_wrong_action() -> None:
    service = AssessmentService.__new__(AssessmentService)
    session_id = uuid4()
    step = ScenarioExpectedAction(
        id=uuid4(),
        scenario_id=uuid4(),
        step_code="set-frc404",
        equipment_id="FRC404",
        action="set",
        payload_constraints={"value": {"min": 40, "max": 60}},
        condition={},
        allowed_delay_ms=5_000,
        severity_if_missed="warning",
        order_index=1,
    )
    event = _event(
        equipment_id="FRC404",
        action="set",
        offset_ms=1_000,
        payload={"value": 80},
    )
    event.session_id = session_id

    errors, matched_steps, _ = service._evaluate(
        session_id=session_id,
        expected_actions=[step],
        operator_events=[event],
        session_started=None,
        is_final=False,
    )

    assert matched_steps == 0
    assert len(errors) == 1
    assert errors[0].error_type == OperatorErrorType.WRONG_ACTION
    assert errors[0].evidence["reason"] == "payload_constraint_violation"
