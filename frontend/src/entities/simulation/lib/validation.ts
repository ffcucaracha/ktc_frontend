import type {
  Alarm,
  AlarmSeverity,
  EquipmentState,
  EquipmentStatus,
  SimulationEvent,
  SimulationEventType,
  SimulationState,
} from "../api/types";

const eventTypes = new Set<SimulationEventType>([
  "session.ready",
  "state.snapshot",
  "state.patch",
  "command.accepted",
  "command.rejected",
  "alarm.raised",
  "alarm.cleared",
  "integration.error",
  "session.completed",
  "session.failed",
]);

const equipmentStatuses = new Set<EquipmentStatus>([
  "stopped",
  "starting",
  "running",
  "stopping",
  "fault",
  "unavailable",
]);

const alarmSeverities = new Set<AlarmSeverity>(["info", "warning", "critical"]);

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function readEquipment(value: unknown): EquipmentState | null {
  if (!isObject(value)) {
    return null;
  }
  const status = value.status;
  const flow = value.flow_kg_h;
  if (
    typeof status !== "string" ||
    !equipmentStatuses.has(status as EquipmentStatus) ||
    !isNumber(flow)
  ) {
    return null;
  }
  return { status: status as EquipmentStatus, flow_kg_h: flow };
}

export function parseAlarm(value: unknown): Alarm | null {
  if (!isObject(value)) {
    return null;
  }
  const { code, severity, message, active } = value;
  if (
    typeof code !== "string" ||
    typeof severity !== "string" ||
    !alarmSeverities.has(severity as AlarmSeverity) ||
    typeof message !== "string" ||
    typeof active !== "boolean"
  ) {
    return null;
  }
  return { code, severity: severity as AlarmSeverity, message, active };
}

export function parseSimulationState(value: unknown): SimulationState | null {
  if (!isObject(value)) {
    return null;
  }
  const { revision, simulation_time_ms: simulationTimeMs, boiler, equipment, alarms } = value;
  if (
    typeof revision !== "number" ||
    !Number.isInteger(revision) ||
    typeof simulationTimeMs !== "number" ||
    !Number.isInteger(simulationTimeMs) ||
    !isObject(boiler) ||
    !isObject(equipment)
  ) {
    return null;
  }
  const temperature = boiler.temperature_c;
  const pressure = boiler.pressure_bar;
  const boilerStatus = boiler.status;
  if (!isNumber(temperature) || !isNumber(pressure) || typeof boilerStatus !== "string") {
    return null;
  }
  const parsedEquipment: Record<string, EquipmentState> = {};
  for (const [equipmentId, equipmentValue] of Object.entries(equipment)) {
    const parsed = readEquipment(equipmentValue);
    if (parsed === null) {
      return null;
    }
    parsedEquipment[equipmentId] = parsed;
  }
  if (!Array.isArray(alarms)) {
    return null;
  }
  const parsedAlarms: Alarm[] = [];
  for (const alarm of alarms) {
    const parsed = parseAlarm(alarm);
    if (parsed === null) {
      return null;
    }
    parsedAlarms.push(parsed);
  }
  const process = isObject(value.process) ? value.process : undefined;
  return {
    revision,
    simulation_time_ms: simulationTimeMs,
    boiler: {
      temperature_c: temperature,
      pressure_bar: pressure,
      status: boilerStatus,
    },
    equipment: parsedEquipment,
    alarms: parsedAlarms,
    ...(process === undefined ? {} : { process }),
  };
}

export function parseSimulationEvent(value: unknown): SimulationEvent | null {
  if (
    !isObject(value) ||
    typeof value.type !== "string" ||
    !eventTypes.has(value.type as SimulationEventType) ||
    !isObject(value.data)
  ) {
    return null;
  }
  return {
    type: value.type as SimulationEventType,
    data: value.data,
  };
}

export function readStringData(data: Record<string, unknown>, field: string): string | null {
  const value = data[field];
  return typeof value === "string" ? value : null;
}
