from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from app.features.risk import FEATURE_NAMES, extract_risk_features
from app.schemas.contracts import OperatorProfile, RecentAction, RiskPredictionRequest, TelemetryPoint

HORIZON_MS = 10_000
WINDOW_MS = 10_000


def build_rows(session: dict[str, Any]) -> list[dict[str, object]]:
    """Convert one chronological digital-twin session export into leakage-safe training rows."""
    session_id = UUID(str(session["session_id"]))
    scenario_code = str(session["scenario_code"])
    snapshots = [TelemetryPoint.model_validate(item) for item in session.get("snapshots", [])]
    actions = [RecentAction.model_validate(item) for item in session.get("actions", [])]
    errors = [item for item in session.get("errors", []) if isinstance(item, dict)]
    profile = OperatorProfile.model_validate(session.get("operator_profile", {}))

    rows: list[dict[str, object]] = []
    for current in sorted(snapshots, key=lambda item: item.simulation_time_ms):
        now_ms = current.simulation_time_ms
        window = [
            item for item in snapshots if now_ms - WINDOW_MS <= item.simulation_time_ms <= now_ms
        ]
        recent_actions = [
            item
            for item in actions
            if item.simulation_time_ms is not None and item.simulation_time_ms <= now_ms
        ]
        request = RiskPredictionRequest(
            session_id=session_id,
            scenario_code=scenario_code,
            operator_profile=profile,
            window=window,
            recent_actions=recent_actions,
        )
        features = extract_risk_features(request)
        future_errors = [
            item
            for item in errors
            if isinstance(item.get("occurred_at_ms"), int)
            and now_ms < int(item["occurred_at_ms"]) <= now_ms + HORIZON_MS
        ]
        error_code = ""
        if future_errors:
            error_code = str(
                future_errors[0].get("error_code", future_errors[0].get("error_type", ""))
            )
        rows.append(
            {
                "session_id": str(session_id),
                "scenario_code": scenario_code,
                "simulation_time_ms": now_ms,
                **features,
                "target_error_next_10s": int(bool(future_errors)),
                "future_error_code": error_code,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a risk dataset from exported digital-twin snapshots/actions/errors. "
            "Only information available at each prediction timestamp is used as features."
        )
    )
    parser.add_argument("input", type=Path, help="JSONL with one exported session per line")
    parser.add_argument("output", type=Path, help="Output CSV")
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    with args.input.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                rows.extend(build_rows(json.loads(line)))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "session_id",
        "scenario_code",
        "simulation_time_ms",
        *FEATURE_NAMES,
        "target_error_next_10s",
        "future_error_code",
    ]
    with args.output.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
