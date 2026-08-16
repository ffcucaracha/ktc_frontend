from __future__ import annotations

from app.schemas.contracts import RiskPredictionRequest, TelemetryPoint

PRESSURE_SENSOR = "PRA351"
TEMPERATURE_SENSOR = "TR41_1"
FEATURE_NAMES = [
    "current_pressure",
    "pressure_delta_5s",
    "pressure_delta_10s",
    "current_temperature",
    "temperature_delta_10s",
    "pump_h1a",
    "pump_h1b",
    "pump_h1v",
    "regulator_frc404",
    "regulator_frc405",
    "regulator_frc406",
    "active_alarm_count",
    "time_since_alarm_s",
    "time_since_last_action_s",
    "action_count_last_10s",
    "scenario_step",
    "previous_errors_total",
    "previous_late_action_count",
    "previous_wrong_action_count",
    "previous_wrong_sequence_count",
    "previous_missed_action_count",
]


def extract_risk_features(request: RiskPredictionRequest) -> dict[str, float]:
    """Build only features observable at prediction time to avoid target leakage."""
    if not request.window:
        return {name: 0.0 for name in FEATURE_NAMES}

    window = sorted(request.window, key=lambda item: item.simulation_time_ms)
    current = window[-1]
    now_ms = current.simulation_time_ms
    previous_errors = request.operator_profile.previous_errors

    actions = [
        item
        for item in request.recent_actions
        if item.simulation_time_ms is not None and item.simulation_time_ms <= now_ms
    ]
    recent_actions = [
        item
        for item in actions
        if item.simulation_time_ms is not None and now_ms - item.simulation_time_ms <= 10_000
    ]
    latest_action_ms = max(
        (item.simulation_time_ms for item in actions if item.simulation_time_ms is not None),
        default=None,
    )
    time_since_last_action_s = (
        max(0, now_ms - latest_action_ms) / 1000.0 if latest_action_ms is not None else 60.0
    )

    alarm_times = _alarm_times(window, now_ms)
    if alarm_times:
        time_since_alarm_s = max(0, now_ms - max(alarm_times)) / 1000.0
    elif current.alarms:
        time_since_alarm_s = 0.0
    else:
        time_since_alarm_s = 60.0

    pressure = _sensor(current, PRESSURE_SENSOR)
    temperature = _sensor(current, TEMPERATURE_SENSOR)
    point_5s = _point_at_or_before(window, now_ms - 5_000)
    point_10s = _point_at_or_before(window, now_ms - 10_000)

    return {
        "current_pressure": pressure,
        "pressure_delta_5s": pressure - _sensor(point_5s, PRESSURE_SENSOR),
        "pressure_delta_10s": pressure - _sensor(point_10s, PRESSURE_SENSOR),
        "current_temperature": temperature,
        "temperature_delta_10s": temperature - _sensor(point_10s, TEMPERATURE_SENSOR),
        "pump_h1a": float(current.pumps.get("H1A", False)),
        "pump_h1b": float(current.pumps.get("H1B", False)),
        "pump_h1v": float(current.pumps.get("H1V", False)),
        "regulator_frc404": float(current.regulators.get("FRC404", 0.0)),
        "regulator_frc405": float(current.regulators.get("FRC405", 0.0)),
        "regulator_frc406": float(current.regulators.get("FRC406", 0.0)),
        "active_alarm_count": float(len(current.alarms)),
        "time_since_alarm_s": time_since_alarm_s,
        "time_since_last_action_s": time_since_last_action_s,
        "action_count_last_10s": float(len(recent_actions)),
        "scenario_step": float(len(actions)),
        "previous_errors_total": float(sum(previous_errors.values())),
        "previous_late_action_count": float(previous_errors.get("LATE_ACTION", 0)),
        "previous_wrong_action_count": float(previous_errors.get("WRONG_ACTION", 0)),
        "previous_wrong_sequence_count": float(previous_errors.get("WRONG_SEQUENCE", 0)),
        "previous_missed_action_count": float(previous_errors.get("MISSED_ACTION", 0)),
    }


def feature_vector(features: dict[str, float]) -> list[float]:
    return [features[name] for name in FEATURE_NAMES]


def _point_at_or_before(window: list[TelemetryPoint], target_ms: int) -> TelemetryPoint:
    candidates = [item for item in window if item.simulation_time_ms <= target_ms]
    return candidates[-1] if candidates else window[0]


def _sensor(point: TelemetryPoint, name: str) -> float:
    return float(point.sensors.get(name, 0.0))


def _alarm_times(window: list[TelemetryPoint], now_ms: int) -> list[int]:
    result: list[int] = []
    for point in window:
        if point.simulation_time_ms > now_ms:
            continue
        for alarm in point.alarms:
            value = alarm.get("simulation_time_ms", alarm.get("raised_at_ms"))
            if isinstance(value, int) and value <= now_ms:
                result.append(value)
    return result
