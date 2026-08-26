import type { AICoachMessage, RiskPrediction } from "../api/types";

const featureLabels: Record<string, string> = {
  current_pressure: "текущее давление",
  pressure_delta_5s: "изменение давления за 5 с",
  pressure_delta_10s: "изменение давления за 10 с",
  current_temperature: "текущая температура",
  temperature_delta_10s: "изменение температуры за 10 с",
  time_since_last_action_s: "время с последнего действия",
  action_count_last_10s: "частота действий оператора",
  active_alarm_count: "активные сигналы",
  scenario_step: "текущий шаг сценария",
};

export function formatRiskPercent(risk: number): string {
  return `${Math.round(Math.max(0, Math.min(1, risk)) * 100)}%`;
}

export function formatFeatureName(name: string): string {
  return featureLabels[name] ?? name.replaceAll("_", " ");
}

export function buildCoachMessage(prediction: RiskPrediction, updatedAt = new Date()): AICoachMessage {
  const topFeature = prediction.features[0];
  const riskPercent = formatRiskPercent(prediction.risk);
  const elevated = prediction.decision_threshold !== null
    ? prediction.risk >= prediction.decision_threshold
    : prediction.predicted_error_code !== null;
  const title = elevated
    ? `Повышенный риск ошибки: ${riskPercent}`
    : `Риск ошибки: ${riskPercent}`;
  const reason = topFeature === undefined
    ? "Модель не выделила доминирующий фактор риска."
    : `Наибольший вклад сейчас вносит: ${formatFeatureName(topFeature.name)}.`;
  const recommendation = elevated
    ? "Контролируйте порядок действий и время реакции на следующем шаге."
    : "Продолжайте работу по текущему сценарию без изменения технологических действий из-за AI-подсказки.";

  return {
    risk: prediction.risk,
    title,
    reason,
    recommendation,
    predictedErrorCode: prediction.predicted_error_code,
    modelVersion: prediction.model_version,
    decisionThreshold: prediction.decision_threshold,
    elevated,
    updatedAt,
  };
}

export function isRiskModelUnavailable(modelVersion: string): boolean {
  return modelVersion.includes("unavailable");
}

export function isMockRiskModel(modelVersion: string): boolean {
  return modelVersion.startsWith("mock-");
}
