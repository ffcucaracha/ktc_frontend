import type { TrainingResult } from "../api/types";

export interface OperatorTrainingStats {
  sessions: number;
  averageScore: number | null;
  averageReactionTimeMs: number | null;
  criticalErrors: number;
}

export function aggregateOperatorTrainingStats(results: TrainingResult[]): OperatorTrainingStats {
  if (results.length === 0) {
    return { sessions: 0, averageScore: null, averageReactionTimeMs: null, criticalErrors: 0 };
  }
  const reactionTimes = results
    .map((item) => item.reaction_time_ms)
    .filter((value): value is number => value !== null);
  return {
    sessions: results.length,
    averageScore: results.reduce((sum, item) => sum + item.score, 0) / results.length,
    averageReactionTimeMs:
      reactionTimes.length === 0
        ? null
        : reactionTimes.reduce((sum, value) => sum + value, 0) / reactionTimes.length,
    criticalErrors: results.reduce((sum, item) => sum + item.critical_error_count, 0),
  };
}

export function formatScore(value: number | null): string {
  return value === null ? "Нет данных" : value.toFixed(1);
}

export function formatReactionTime(value: number | null): string {
  return value === null ? "Нет данных" : `${(value / 1000).toFixed(2)} с`;
}
