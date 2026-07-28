import { ApiClientError } from "../../../shared/api/client";
import type { SimulationSessionStatus } from "../api/types";

export function formatSessionStatus(status: SimulationSessionStatus): string {
  const labels: Record<SimulationSessionStatus, string> = {
    creating: "Создаётся",
    active: "Активна",
    stopping: "Останавливается",
    completed: "Завершена",
    failed: "Ошибка",
  };
  return labels[status];
}

export function describeSimulationError(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.code === "SIMULATION_TIMEOUT") {
      return "Сервис моделирования не ответил вовремя. Повторите попытку позже.";
    }
    if (error.code === "SIMULATION_SERVICE_UNAVAILABLE") {
      return "Сервис моделирования сейчас недоступен.";
    }
    if (
      error.code === "SIMULATION_PROTOCOL_ERROR" ||
      error.code === "INVALID_EXTERNAL_PAYLOAD"
    ) {
      return "Сервис моделирования вернул некорректный ответ.";
    }
    return error.message;
  }
  return "Не удалось выполнить операцию.";
}

export function describeSessionFailure(errorCode: string | null): string {
  if (errorCode === "SIMULATION_TIMEOUT") {
    return "Сервис моделирования не ответил вовремя. Сессия не запущена.";
  }
  if (errorCode === "SIMULATION_SERVICE_UNAVAILABLE") {
    return "Сервис моделирования недоступен. Сессия не запущена.";
  }
  if (errorCode === "SIMULATION_PROTOCOL_ERROR" || errorCode === "INVALID_EXTERNAL_PAYLOAD") {
    return "Сервис моделирования вернул некорректный ответ. Сессия не запущена.";
  }
  return "Сессия не запущена из-за ошибки сервиса моделирования.";
}
