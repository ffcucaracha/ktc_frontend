from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import (
    OperatorError,
    OperatorErrorType,
    SimulationEvent,
    SimulationSession,
    SimulationSessionStatus,
    SimulationTimelineEventType,
    TrainingScenario,
)


async def export_sessions(session: AsyncSession, output: Path) -> int:
    result = await session.execute(
        select(SimulationSession, TrainingScenario.code)
        .join(TrainingScenario, TrainingScenario.id == SimulationSession.training_scenario_id)
        .where(
            SimulationSession.status.in_(
                [SimulationSessionStatus.COMPLETED, SimulationSessionStatus.FAILED]
            ),
            SimulationSession.training_scenario_id.is_not(None),
        )
        .order_by(SimulationSession.started_at.asc(), SimulationSession.id.asc())
    )
    sessions = list(result.all())

    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with output.open("w", encoding="utf-8") as target:
        for simulation_session, scenario_code in sessions:
            payload = await build_session_export(session, simulation_session, scenario_code)
            if payload is None:
                continue
            target.write(json.dumps(payload, ensure_ascii=False) + "\n")
            written += 1
    return written


async def build_session_export(
    session: AsyncSession,
    simulation_session: SimulationSession,
    scenario_code: str,
) -> dict[str, object] | None:
    timeline_result = await session.execute(
        select(SimulationEvent)
        .where(SimulationEvent.session_id == simulation_session.id)
        .order_by(SimulationEvent.created_at.asc(), SimulationEvent.id.asc())
    )
    timeline = list(timeline_result.scalars())
    snapshot_events = [
        item
        for item in timeline
        if item.event_type == SimulationTimelineEventType.STATE_SNAPSHOT
    ]
    if not snapshot_events:
        return None

    error_result = await session.execute(
        select(OperatorError)
        .where(OperatorError.session_id == simulation_session.id)
        .order_by(OperatorError.occurred_at_ms.asc().nullslast(), OperatorError.created_at.asc())
    )
    errors = list(error_result.scalars())

    previous_errors = await _previous_error_counts(session, simulation_session)
    snapshots = [normalise_snapshot(item) for item in snapshot_events]
    actions = [
        normalise_action(item)
        for item in timeline
        if item.event_type == SimulationTimelineEventType.OPERATOR_COMMAND
    ]
    return {
        "session_id": str(simulation_session.id),
        "scenario_code": scenario_code,
        "operator_profile": {"previous_errors": previous_errors},
        "snapshots": snapshots,
        "actions": actions,
        "errors": [
            {
                "occurred_at_ms": item.occurred_at_ms,
                "error_code": _error_type_value(item.error_type),
            }
            for item in errors
            if item.occurred_at_ms is not None
        ],
    }


async def _previous_error_counts(
    session: AsyncSession,
    current: SimulationSession,
) -> dict[str, int]:
    if current.started_at is None:
        return {}
    result = await session.execute(
        select(OperatorError)
        .join(SimulationSession, SimulationSession.id == OperatorError.session_id)
        .where(
            SimulationSession.operator_id == current.operator_id,
            SimulationSession.id != current.id,
            SimulationSession.started_at.is_not(None),
            SimulationSession.started_at < current.started_at,
        )
    )
    counter = Counter(_error_type_value(item.error_type) for item in result.scalars())
    return dict(sorted(counter.items()))


def _error_type_value(error_type: OperatorErrorType | str) -> str:
    return error_type.value if isinstance(error_type, OperatorErrorType) else str(error_type)


def normalise_snapshot(event: SimulationEvent) -> dict[str, object]:
    payload = event.payload
    process = payload.get("process") if isinstance(payload.get("process"), dict) else {}
    raw = process.get("raw") if isinstance(process, dict) and isinstance(process.get("raw"), dict) else {}

    sensors = _merged_numeric_mapping(
        _mapping(process, "sensors"),
        _mapping(process, "sensors_in"),
        _mapping(process, "flow_meters"),
        _mapping(process, "collector"),
        _mapping(process, "output"),
        _mapping(process, "combined"),
        _mapping(raw, "sensors"),
    )
    pumps = _mapping(process, "pumps") or _mapping(raw, "pumps")
    valves = _mapping(process, "valves") or _mapping(raw, "valves")
    regulators = _mapping(process, "regulators") or _mapping(raw, "regulators")
    dosing = _mapping(process, "dosing") or _mapping(raw, "dosing")
    elou = _mapping(process, "elou")
    alarms = payload.get("alarms") if isinstance(payload.get("alarms"), list) else []

    revision = event.revision
    if revision is None:
        value = payload.get("revision")
        revision = value if isinstance(value, int) else 0
    simulation_time_ms = event.simulation_time_ms
    if simulation_time_ms is None:
        value = payload.get("simulation_time_ms")
        simulation_time_ms = value if isinstance(value, int) else 0

    return {
        "simulation_time_ms": simulation_time_ms,
        "revision": revision,
        "sensors": sensors,
        "pumps": _boolean_mapping(pumps),
        "valves": _boolean_mapping(valves),
        "regulators": _numeric_mapping(regulators),
        "dosing": _json_scalar_mapping(dosing),
        "elou": _json_scalar_mapping(elou),
        "alarms": alarms,
    }


def normalise_action(event: SimulationEvent) -> dict[str, object]:
    payload = event.payload
    command_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    return {
        "simulation_time_ms": event.simulation_time_ms,
        "equipment_id": str(payload.get("equipment_id", "")),
        "action": str(payload.get("action", "")),
        "payload": command_payload,
    }


def _mapping(source: object, key: str) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    value = source.get(key)
    return value if isinstance(value, dict) else {}


def _numeric_mapping(source: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, value in source.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[str(key)] = float(value)
    return result


def _merged_numeric_mapping(*sources: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for source in sources:
        result.update(_numeric_mapping(source))
    return result


def _boolean_mapping(source: dict[str, Any]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for key, value in source.items():
        if isinstance(value, bool):
            result[str(key)] = value
    return result


def _json_scalar_mapping(source: dict[str, Any]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in source.items():
        if isinstance(value, bool) or (
            isinstance(value, (int, float, str)) and not isinstance(value, bool)
        ):
            result[str(key)] = value
    return result


async def _run(output: Path) -> int:
    async with AsyncSessionLocal() as session:
        return await export_sessions(session, output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export completed scenario sessions to leakage-safe ML JSONL"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/session_exports.jsonl"),
        help="Output JSONL path",
    )
    args = parser.parse_args()
    written = asyncio.run(_run(args.output))
    print(f"Exported {written} sessions to {args.output}")


if __name__ == "__main__":
    main()
