from __future__ import annotations

from app.schemas.contracts import RecentAction, RiskPredictionRequest, TelemetryPoint

FEATURE_NAMES = [
    "current_pressure",
    "pressure_delta_5s",
    "pressure_delta_10s",
    "current_temperature",
    "temperature_delta_10s",
    "oil_flow_after_pumps",
    "oil_flow_to_elou",
    "oil_elou_flow_gap",
    "pump_h1a",
    "pump_h1b",
    "pump_h1c",
    "pump_nd1",
    "pump_nd2",
    "pump_h3",
    "valve_kr1",
    "valve_kr6",
    "valve_kr7",
    "valve_kr8",
    "regulator_frc404",
    "regulator_frc405",
    "regulator_frc406",
    "regulator_frc407",
    "regulator_frc408",
    "nd1_flow",
    "nd1_target",
    "nd1_setpoint_error",
    "nd2_flow",
    "nd2_setpoint_error",
    "water_flow",
    "e1_level",
    "e1_ready",
    "e1_voltage",
    "po1_level",
    "combined_scenario",
    "recent_action_h1c",
    "recent_action_nd1",
    "recent_action_kr1",
    "recent_action_kr6",
    "recent_action_frc404",
    "recent_action_frc407",
    "recent_action_nd2",
    "recent_action_frc408",
    "recent_action_e1_voltage",
    "recent_action_kr7",
    "recent_action_kr8",
    "last_setpoint_nd1",
    "last_setpoint_frc404",
    "last_setpoint_frc407",
    "last_setpoint_nd2",
    "last_setpoint_frc408",
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

    pressure = _first_sensor(current, "PRA1", "PRA351")
    temperature = _first_sensor(current, "TR2", "TR41_1", "TR1")
    point_5s = _point_at_or_before(window, now_ms - 5_000)
    point_10s = _point_at_or_before(window, now_ms - 10_000)
    oil_flow_after_pumps = sum(
        _first_sensor(current, key)
        for key in ("FQR117_1", "FQR117_2", "FQR117_3")
    )
    oil_flow_to_elou = _elou_number(current, "FQR118", fallback_key="elou_input_flow")
    e1_level = _elou_number(current, "E1_level")
    nd1_flow = _number(current.dosing.get("ND1_flow"))
    nd1_target = _number(current.dosing.get("ND1_target"))
    nd2_flow = _elou_number(current, "ND2_flow")

    return {
        "current_pressure": pressure,
        "pressure_delta_5s": pressure - _first_sensor(point_5s, "PRA1", "PRA351"),
        "pressure_delta_10s": pressure - _first_sensor(point_10s, "PRA1", "PRA351"),
        "current_temperature": temperature,
        "temperature_delta_10s": temperature - _first_sensor(point_10s, "TR2", "TR41_1", "TR1"),
        "oil_flow_after_pumps": oil_flow_after_pumps,
        "oil_flow_to_elou": oil_flow_to_elou,
        "oil_elou_flow_gap": oil_flow_after_pumps - oil_flow_to_elou,
        "pump_h1a": float(current.pumps.get("H1A", False)),
        "pump_h1b": float(current.pumps.get("H1B", False)),
        "pump_h1c": float(current.pumps.get("H1C", current.pumps.get("H1V", False))),
        "pump_nd1": float(current.pumps.get("ND1", False)),
        "pump_nd2": _elou_bool(current, "ND2"),
        "pump_h3": _elou_bool(current, "H3"),
        "valve_kr1": float(current.valves.get("KR1", False)),
        "valve_kr6": float(current.valves.get("KR6", False)),
        "valve_kr7": _elou_bool(current, "KR7"),
        "valve_kr8": _elou_bool(current, "KR8"),
        "regulator_frc404": float(current.regulators.get("FRC404", 0.0)),
        "regulator_frc405": float(current.regulators.get("FRC405", 0.0)),
        "regulator_frc406": float(current.regulators.get("FRC406", 0.0)),
        "regulator_frc407": _elou_number(current, "FRC407_valve"),
        "regulator_frc408": _elou_number(current, "FRC408_valve"),
        "nd1_flow": nd1_flow,
        "nd1_target": nd1_target,
        "nd1_setpoint_error": float(current.dosing.get("ND1_error") is True),
        "nd2_flow": nd2_flow,
        "nd2_setpoint_error": _elou_bool(current, "ND2_error"),
        "water_flow": _elou_number(current, "water_flow"),
        "e1_level": e1_level,
        "e1_ready": _elou_bool(current, "E1_ready"),
        "e1_voltage": _elou_bool(current, "E1_voltage"),
        "po1_level": _elou_number(current, "PO1_level"),
        "combined_scenario": float("elou" in request.scenario_code),
        "recent_action_h1c": _recent_equipment_count(recent_actions, "H1C"),
        "recent_action_nd1": _recent_equipment_count(recent_actions, "ND1"),
        "recent_action_kr1": _recent_equipment_count(recent_actions, "KR1"),
        "recent_action_kr6": _recent_equipment_count(recent_actions, "KR6"),
        "recent_action_frc404": _recent_equipment_count(recent_actions, "FRC404"),
        "recent_action_frc407": _recent_equipment_count(recent_actions, "FRC407"),
        "recent_action_nd2": _recent_equipment_count(recent_actions, "ND2"),
        "recent_action_frc408": _recent_equipment_count(recent_actions, "FRC408"),
        "recent_action_e1_voltage": _recent_action_count(recent_actions, "E1", "apply_voltage"),
        "recent_action_kr7": _recent_equipment_count(recent_actions, "KR7"),
        "recent_action_kr8": _recent_equipment_count(recent_actions, "KR8"),
        "last_setpoint_nd1": _last_payload_value(actions, "ND1"),
        "last_setpoint_frc404": _last_payload_value(actions, "FRC404"),
        "last_setpoint_frc407": _last_payload_value(actions, "FRC407"),
        "last_setpoint_nd2": _last_payload_value(actions, "ND2"),
        "last_setpoint_frc408": _last_payload_value(actions, "FRC408"),
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


def _first_sensor(point: TelemetryPoint, *names: str) -> float:
    for name in names:
        if name in point.sensors:
            return float(point.sensors[name])
    return 0.0


def _number(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _elou_number(point: TelemetryPoint, key: str, *, fallback_key: str | None = None) -> float:
    if key in point.elou:
        return _number(point.elou[key])
    if fallback_key is not None:
        return _first_sensor(point, fallback_key)
    return 0.0


def _elou_bool(point: TelemetryPoint, key: str) -> float:
    return float(point.elou.get(key) is True)


def _recent_equipment_count(actions: list[RecentAction], equipment_id: str) -> float:
    return float(sum(1 for item in actions if item.equipment_id == equipment_id))


def _recent_action_count(actions: list[RecentAction], equipment_id: str, action: str) -> float:
    return float(
        sum(1 for item in actions if item.equipment_id == equipment_id and item.action == action)
    )


def _last_payload_value(actions: list[RecentAction], equipment_id: str) -> float:
    for item in reversed(actions):
        if item.equipment_id != equipment_id:
            continue
        value = item.payload.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


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
