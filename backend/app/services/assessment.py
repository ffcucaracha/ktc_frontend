from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OperatorError,
    OperatorErrorSource,
    OperatorErrorType,
    ScenarioExpectedAction,
    SimulationEvent,
    SimulationSessionStatus,
    SimulationTimelineEventType,
    TrainingResult,
)
from app.repositories.assessment import AssessmentRepository
from app.repositories.simulation_events import SimulationEventRepository
from app.repositories.simulation_sessions import SimulationSessionRepository
from app.repositories.training_scenarios import TrainingScenarioRepository

RULE_VERSION = "assessment-rules-v1"
ERROR_PENALTIES = {
    OperatorErrorType.WRONG_ACTION: 10.0,
    OperatorErrorType.WRONG_SEQUENCE: 15.0,
    OperatorErrorType.LATE_ACTION: 10.0,
    OperatorErrorType.MISSED_ACTION: 20.0,
}


class AssessmentSessionNotFoundError(Exception):
    pass


class AssessmentScenarioRequiredError(Exception):
    pass


@dataclass(frozen=True)
class AssessmentOutcome:
    result: TrainingResult
    errors: list[OperatorError]


class AssessmentService:
    """Deterministic assessment of operator actions against scenario ground truth."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._sessions = SimulationSessionRepository(session)
        self._events = SimulationEventRepository(session)
        self._scenarios = TrainingScenarioRepository(session)
        self._assessment = AssessmentRepository(session)

    async def assess_session(self, session_id: UUID, operator_id: UUID) -> AssessmentOutcome:
        simulation_session = await self._sessions.get_for_operator(session_id, operator_id)
        if simulation_session is None:
            raise AssessmentSessionNotFoundError
        if simulation_session.training_scenario_id is None:
            raise AssessmentScenarioRequiredError

        expected_actions = await self._scenarios.list_expected_actions(
            simulation_session.training_scenario_id
        )
        timeline = await self._events.list_for_session(session_id)
        operator_events = [
            item
            for item in timeline
            if item.event_type == SimulationTimelineEventType.OPERATOR_COMMAND
        ]
        session_started = next(
            (item for item in timeline if item.event_type == SimulationTimelineEventType.SESSION_STARTED),
            None,
        )
        is_final = simulation_session.status in {
            SimulationSessionStatus.COMPLETED,
            SimulationSessionStatus.FAILED,
        }

        errors, matched_steps, delays = self._evaluate(
            session_id=session_id,
            expected_actions=expected_actions,
            operator_events=operator_events,
            session_started=session_started,
            is_final=is_final,
        )
        stored_errors = await self._assessment.replace_errors(session_id, errors)

        counts = {error_type: 0 for error_type in OperatorErrorType}
        for item in stored_errors:
            counts[item.error_type] += 1

        score = max(
            0.0,
            100.0 - sum(ERROR_PENALTIES[item.error_type] for item in stored_errors),
        )
        sequence_score = max(
            0.0,
            100.0
            - counts[OperatorErrorType.WRONG_SEQUENCE] * 25.0
            - counts[OperatorErrorType.WRONG_ACTION] * 10.0,
        )
        reaction_score = max(
            0.0,
            100.0
            - counts[OperatorErrorType.LATE_ACTION] * 20.0
            - counts[OperatorErrorType.MISSED_ACTION] * 15.0,
        )
        critical_error_count = sum(1 for item in stored_errors if item.severity == "critical")
        safety_score = max(0.0, 100.0 - critical_error_count * 25.0)
        average_reaction_ms = round(sum(delays) / len(delays)) if delays else None

        summary: dict[str, object] = {
            "rule_version": RULE_VERSION,
            "is_final": is_final,
            "expected_step_count": len(expected_actions),
            "matched_step_count": matched_steps,
            "operator_command_count": len(operator_events),
            "error_counts": {item.value: counts[item] for item in OperatorErrorType},
        }
        result = await self._assessment.upsert_result(
            session_id=session_id,
            scenario_id=simulation_session.training_scenario_id,
            score=score,
            max_score=100.0,
            reaction_time_ms=average_reaction_ms,
            error_count=len(stored_errors),
            critical_error_count=critical_error_count,
            sequence_score=sequence_score,
            reaction_score=reaction_score,
            safety_score=safety_score,
            status="final" if is_final else "provisional",
            summary=summary,
        )
        await self._session.commit()
        return AssessmentOutcome(result=result, errors=stored_errors)

    async def get_assessment(self, session_id: UUID, operator_id: UUID) -> AssessmentOutcome:
        return await self.assess_session(session_id, operator_id)

    def _evaluate(
        self,
        *,
        session_id: UUID,
        expected_actions: list[ScenarioExpectedAction],
        operator_events: list[SimulationEvent],
        session_started: SimulationEvent | None,
        is_final: bool,
    ) -> tuple[list[OperatorError], int, list[int]]:
        errors: list[OperatorError] = []
        expected_index = 0
        matched_steps = 0
        delays: list[int] = []
        anchor_event = session_started

        for event in operator_events:
            command = self._command_from_event(event)
            if command is None:
                continue

            if expected_index >= len(expected_actions):
                errors.append(
                    self._error(
                        session_id=session_id,
                        error_type=OperatorErrorType.WRONG_ACTION,
                        severity="warning",
                        event=event,
                        expected_action=None,
                        evidence={"reason": "unexpected_extra_action", "actual": command},
                    )
                )
                continue

            expected = expected_actions[expected_index]
            exact_action = self._same_action(expected, command)
            payload_valid = exact_action and self._payload_matches(
                expected.payload_constraints,
                command["payload"],
            )

            if exact_action and payload_valid:
                delay_ms = self._delay_ms(anchor_event, event)
                delays.append(delay_ms)
                if expected.allowed_delay_ms is not None and delay_ms > expected.allowed_delay_ms:
                    errors.append(
                        self._error(
                            session_id=session_id,
                            error_type=OperatorErrorType.LATE_ACTION,
                            severity=expected.severity_if_missed,
                            event=event,
                            expected_action=expected,
                            evidence={
                                "reason": "allowed_delay_exceeded",
                                "delay_ms": delay_ms,
                                "allowed_delay_ms": expected.allowed_delay_ms,
                                "actual": command,
                            },
                        )
                    )
                expected_index += 1
                matched_steps += 1
                anchor_event = event
                continue

            if exact_action and not payload_valid:
                errors.append(
                    self._error(
                        session_id=session_id,
                        error_type=OperatorErrorType.WRONG_ACTION,
                        severity=expected.severity_if_missed,
                        event=event,
                        expected_action=expected,
                        evidence={
                            "reason": "payload_constraint_violation",
                            "constraints": expected.payload_constraints or {},
                            "actual": command,
                        },
                    )
                )
                continue

            later = next(
                (
                    item
                    for item in expected_actions[expected_index + 1 :]
                    if self._same_action(item, command)
                ),
                None,
            )
            if later is not None:
                errors.append(
                    self._error(
                        session_id=session_id,
                        error_type=OperatorErrorType.WRONG_SEQUENCE,
                        severity="warning",
                        event=event,
                        expected_action=expected,
                        evidence={
                            "reason": "later_step_executed_before_current",
                            "expected_step": expected.step_code,
                            "executed_step": later.step_code,
                            "actual": command,
                        },
                    )
                )
            else:
                errors.append(
                    self._error(
                        session_id=session_id,
                        error_type=OperatorErrorType.WRONG_ACTION,
                        severity="warning",
                        event=event,
                        expected_action=expected,
                        evidence={
                            "reason": "action_not_expected_at_current_step",
                            "expected_step": expected.step_code,
                            "actual": command,
                        },
                    )
                )

        if is_final:
            for expected in expected_actions[expected_index:]:
                errors.append(
                    OperatorError(
                        session_id=session_id,
                        scenario_expected_action_id=expected.id,
                        error_type=OperatorErrorType.MISSED_ACTION,
                        severity=expected.severity_if_missed,
                        occurred_at_ms=None,
                        source=OperatorErrorSource.RULE,
                        evidence={
                            "reason": "session_finished_before_expected_action",
                            "expected_step": expected.step_code,
                            "equipment_id": expected.equipment_id,
                            "action": expected.action,
                        },
                        causal_chain=[
                            {"kind": "expected_step", "step_code": expected.step_code},
                            {"kind": "session_finished", "result": "step_not_completed"},
                        ],
                    )
                )

        return errors, matched_steps, delays

    @staticmethod
    def _command_from_event(event: SimulationEvent) -> dict[str, Any] | None:
        equipment_id = event.payload.get("equipment_id")
        action = event.payload.get("action")
        payload = event.payload.get("payload", {})
        if (
            not isinstance(equipment_id, str)
            or not isinstance(action, str)
            or not isinstance(payload, dict)
        ):
            return None
        return {"equipment_id": equipment_id, "action": action, "payload": payload}

    @staticmethod
    def _same_action(expected: ScenarioExpectedAction, command: dict[str, Any]) -> bool:
        return (
            expected.equipment_id == command["equipment_id"]
            and expected.action == command["action"]
        )

    @staticmethod
    def _payload_matches(
        constraints: dict[str, object] | None,
        payload: dict[str, Any],
    ) -> bool:
        if not constraints:
            return True
        for field, rule in constraints.items():
            if field not in payload:
                return False
            value = payload[field]
            if isinstance(rule, dict):
                minimum = rule.get("min")
                maximum = rule.get("max")
                if minimum is not None:
                    if not isinstance(minimum, int | float) or not isinstance(value, int | float):
                        return False
                    if value < minimum:
                        return False
                if maximum is not None:
                    if not isinstance(maximum, int | float) or not isinstance(value, int | float):
                        return False
                    if value > maximum:
                        return False
            elif value != rule:
                return False
        return True

    @staticmethod
    def _delay_ms(previous: SimulationEvent | None, current: SimulationEvent) -> int:
        if previous is None:
            return 0
        if (
            previous.simulation_time_ms is not None
            and current.simulation_time_ms is not None
            and current.simulation_time_ms >= previous.simulation_time_ms
        ):
            return current.simulation_time_ms - previous.simulation_time_ms
        return max(0, round((current.created_at - previous.created_at).total_seconds() * 1000))

    @staticmethod
    def _error(
        *,
        session_id: UUID,
        error_type: OperatorErrorType,
        severity: str,
        event: SimulationEvent,
        expected_action: ScenarioExpectedAction | None,
        evidence: dict[str, object],
    ) -> OperatorError:
        expected_step = expected_action.step_code if expected_action is not None else None
        return OperatorError(
            session_id=session_id,
            scenario_expected_action_id=expected_action.id if expected_action is not None else None,
            error_type=error_type,
            severity=severity,
            occurred_at_ms=event.simulation_time_ms,
            source=OperatorErrorSource.RULE,
            evidence=evidence,
            causal_chain=[
                {"kind": "operator_action", "event_id": str(event.id)},
                {"kind": "rule_check", "rule_version": RULE_VERSION, "expected_step": expected_step},
                {"kind": "classification", "error_type": error_type.value},
            ],
        )
