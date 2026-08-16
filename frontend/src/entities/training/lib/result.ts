import type {
  OperatorError,
  OperatorErrorType,
  SimulationTimelineEvent,
} from "../api/types";

export interface ResultTimelineItem {
  id: string;
  kind: "alarm" | "action" | "state" | "error" | "risk" | "session" | "other";
  simulationTimeMs: number | null;
  createdAt: string;
  title: string;
  detail: string;
  risk?: number;
}

const errorLabels: Record<OperatorErrorType, string> = {
  WRONG_ACTION: "Неверное действие",
  LATE_ACTION: "Поздняя реакция",
  MISSED_ACTION: "Пропущенное действие",
  WRONG_SEQUENCE: "Нарушение последовательности",
};

export function formatDurationMs(value: number | null): string {
  if (value === null) {
    return "нет данных";
  }
  if (value < 1000) {
    return `${value} мс`;
  }
  return `${(value / 1000).toFixed(value >= 10_000 ? 1 : 2)} с`;
}

export function formatScore(score: number, maxScore: number): string {
  return `${Math.round(score)} / ${Math.round(maxScore)}`;
}

export function operatorErrorLabel(type: OperatorErrorType): string {
  return errorLabels[type];
}

export function describeOperatorError(error: OperatorError): string {
  const actual = asRecord(error.evidence.actual);
  const expected = asRecord(error.evidence.expected);
  const equipment = stringValue(actual?.equipment_id) ?? stringValue(error.evidence.equipment_id);
  const actualAction = stringValue(actual?.action);
  const expectedAction = stringValue(expected?.action);

  if (error.error_type === "LATE_ACTION") {
    const delayMs = numberValue(error.evidence.delay_ms);
    return delayMs === null
      ? "Действие было выполнено позже допустимого окна сценария."
      : `Действие выполнено с задержкой ${formatDurationMs(delayMs)} относительно допустимого окна.`;
  }
  if (error.error_type === "MISSED_ACTION") {
    return expectedAction === null
      ? "Обязательный шаг сценария не был выполнен."
      : `Обязательное действие «${expectedAction}» не было выполнено.`;
  }
  if (error.error_type === "WRONG_SEQUENCE") {
    return equipment === null
      ? "Действие выполнено вне требуемой последовательности сценария."
      : `Операция с ${equipment} выполнена вне требуемой последовательности сценария.`;
  }
  if (actualAction !== null && expectedAction !== null) {
    return `Выполнено «${actualAction}», ожидалось «${expectedAction}».`;
  }
  return "Фактическое действие не соответствует ожидаемому шагу сценария.";
}

export function buildResultTimelineItems(
  timeline: SimulationTimelineEvent[],
  errors: OperatorError[],
): ResultTimelineItem[] {
  const items: ResultTimelineItem[] = [];
  let lastSnapshotTime = Number.NEGATIVE_INFINITY;

  for (const event of timeline) {
    const type = event.event_type;
    if (type === "state.snapshot") {
      const time = event.simulation_time_ms;
      if (time !== null && time - lastSnapshotTime < 10_000) {
        continue;
      }
      if (time !== null) {
        lastSnapshotTime = time;
      }
      items.push({
        id: event.id,
        kind: "state",
        simulationTimeMs: event.simulation_time_ms,
        createdAt: event.created_at,
        title: "Состояние установки",
        detail: event.revision === null ? "Сохранён snapshot." : `Revision ${event.revision}.`,
      });
      continue;
    }
    if (type === "operator.command") {
      const equipment = stringValue(event.payload.equipment_id) ?? "оборудование";
      const action = stringValue(event.payload.action) ?? "команда";
      items.push({
        id: event.id,
        kind: "action",
        simulationTimeMs: event.simulation_time_ms,
        createdAt: event.created_at,
        title: `Действие оператора: ${equipment}`,
        detail: action,
      });
      continue;
    }
    if (type === "alarm.raised" || type === "alarm.cleared") {
      const code = stringValue(event.payload.code) ?? "сигнал";
      items.push({
        id: event.id,
        kind: "alarm",
        simulationTimeMs: event.simulation_time_ms,
        createdAt: event.created_at,
        title: type === "alarm.raised" ? `Сигнал ${code}` : `Сигнал ${code} снят`,
        detail: stringValue(event.payload.message) ?? "Событие сигнализации.",
      });
      continue;
    }
    if (type === "ai.risk.updated") {
      const risk = numberValue(event.payload.risk) ?? 0;
      const predicted = stringValue(event.payload.predicted_error_code);
      items.push({
        id: event.id,
        kind: "risk",
        simulationTimeMs: event.simulation_time_ms,
        createdAt: event.created_at,
        title: `Прогноз риска: ${Math.round(Math.max(0, Math.min(1, risk)) * 100)}%`,
        detail: predicted === null ? "Тип ошибки не прогнозировался." : `Прогноз: ${predicted}.`,
        risk,
      });
      continue;
    }
    if (type === "session.started" || type === "session.completed" || type === "session.failed") {
      items.push({
        id: event.id,
        kind: "session",
        simulationTimeMs: event.simulation_time_ms,
        createdAt: event.created_at,
        title: type === "session.started" ? "Сессия начата" : type === "session.completed" ? "Сессия завершена" : "Сессия завершена с ошибкой",
        detail: "Системное событие сессии.",
      });
    }
  }

  for (const error of errors) {
    items.push({
      id: `error-${error.id}`,
      kind: "error",
      simulationTimeMs: error.occurred_at_ms,
      createdAt: error.created_at,
      title: operatorErrorLabel(error.error_type),
      detail: describeOperatorError(error),
    });
  }

  return items.sort((left, right) => {
    if (left.simulationTimeMs !== null && right.simulationTimeMs !== null) {
      const bySimulationTime = left.simulationTimeMs - right.simulationTimeMs;
      if (bySimulationTime !== 0) {
        return bySimulationTime;
      }
    } else if (left.simulationTimeMs !== null) {
      return -1;
    } else if (right.simulationTimeMs !== null) {
      return 1;
    }
    return left.createdAt.localeCompare(right.createdAt);
  });
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
