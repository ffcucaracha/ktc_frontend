import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  LinearProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { Link as RouterLink, useParams } from "react-router-dom";

import { useSimulationSessionQuery } from "../../entities/simulation/model/queries";
import type { OperatorError, SimulationTimelineEvent } from "../../entities/training/api/types";
import {
  useSessionDebriefQuery,
  useSessionTimelineQuery,
  useTrainingAssessmentQuery,
} from "../../entities/training/model/queries";
import {
  describeOperatorError,
  formatDurationMs,
  formatScore,
  operatorErrorLabel,
} from "../../entities/training/lib/result";
import { ErrorView } from "../../shared/ui/ErrorView";
import { LoadingView } from "../../shared/ui/LoadingView";
import { TrainingTimeline } from "../../widgets/training-timeline/TrainingTimeline";

interface MetricCardProps {
  label: string;
  value: string;
  helper?: string;
}

interface PredictionLeadSummary {
  count: number;
  maxRisk: number | null;
  leadMs: number | null;
}

function MetricCard({ label, value, helper }: MetricCardProps): JSX.Element {
  return (
    <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2 }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography variant="h5" sx={{ mt: 0.5 }}>{value}</Typography>
      {helper === undefined ? null : (
        <Typography variant="caption" color="text.secondary">{helper}</Typography>
      )}
    </Paper>
  );
}

function predictionLeadSummary(
  timeline: SimulationTimelineEvent[],
  errors: OperatorError[],
): PredictionLeadSummary {
  const predictions = timeline
    .filter((event) => event.event_type === "ai.risk.updated" && event.simulation_time_ms !== null)
    .map((event) => ({
      time: event.simulation_time_ms as number,
      risk: typeof event.payload.risk === "number" ? event.payload.risk : 0,
      predictedErrorCode:
        typeof event.payload.predicted_error_code === "string"
          ? event.payload.predicted_error_code
          : null,
      horizonSeconds:
        typeof event.payload.horizon_seconds === "number" ? event.payload.horizon_seconds : 10,
    }))
    .filter((prediction) => prediction.predictedErrorCode !== null);

  const matches = errors.flatMap((error) => {
    if (error.occurred_at_ms === null) return [];
    return predictions
      .map((prediction) => ({
        risk: prediction.risk,
        leadMs: (error.occurred_at_ms as number) - prediction.time,
        horizonMs: prediction.horizonSeconds * 1000,
      }))
      .filter((match) => match.leadMs >= 0 && match.leadMs <= match.horizonMs);
  });

  const predictedErrorIds = new Set(
    errors
      .filter((error) => {
        if (error.occurred_at_ms === null) return false;
        return predictions.some((prediction) => {
          const delta = (error.occurred_at_ms as number) - prediction.time;
          return delta >= 0 && delta <= prediction.horizonSeconds * 1000;
        });
      })
      .map((error) => error.id),
  );

  if (matches.length === 0) {
    return { count: 0, maxRisk: null, leadMs: null };
  }

  const strongest = matches.reduce((best, current) =>
    current.risk > best.risk ? current : best,
  );

  return {
    count: predictedErrorIds.size,
    maxRisk: strongest.risk,
    leadMs: strongest.leadMs,
  };
}

export function OperatorSessionResultPage(): JSX.Element {
  const { sessionId } = useParams();
  const resolvedSessionId = sessionId ?? "";
  const sessionQuery = useSimulationSessionQuery(resolvedSessionId);
  const assessmentQuery = useTrainingAssessmentQuery(resolvedSessionId);
  const timelineQuery = useSessionTimelineQuery(resolvedSessionId);
  const debriefQuery = useSessionDebriefQuery(resolvedSessionId);

  if (sessionId === undefined) {
    return <ErrorView title="Результат не найден" message="Некорректный адрес страницы." />;
  }

  if (
    sessionQuery.isLoading ||
    assessmentQuery.isLoading ||
    timelineQuery.isLoading ||
    debriefQuery.isLoading
  ) {
    return <LoadingView message="Формируем итоговый разбор тренировки" />;
  }

  if (
    sessionQuery.isError ||
    assessmentQuery.isError ||
    timelineQuery.isError ||
    debriefQuery.isError ||
    sessionQuery.data === undefined ||
    assessmentQuery.data === undefined ||
    timelineQuery.data === undefined ||
    debriefQuery.data === undefined
  ) {
    return (
      <ErrorView
        title="Не удалось загрузить разбор"
        message="Итоговые данные временно недоступны. Завершённая сессия сохранена и разбор можно открыть повторно."
        actionLabel="Повторить"
        onAction={() => {
          void Promise.all([
            sessionQuery.refetch(),
            assessmentQuery.refetch(),
            timelineQuery.refetch(),
            debriefQuery.refetch(),
          ]);
        }}
      />
    );
  }

  const session = sessionQuery.data;
  const assessment = assessmentQuery.data;
  const result = assessment.result;
  const errors = assessment.errors;
  const timeline = timelineQuery.data;
  const debrief = debriefQuery.data;
  const predictionSummary = predictionLeadSummary(timeline, errors);
  const scorePercent = result.max_score <= 0 ? 0 : Math.max(0, Math.min(100, (result.score / result.max_score) * 100));
  const nextTraining = debrief.recommendations[0] ?? "Закрепить результат повторным прохождением сценария.";
  const recommendedScenarioPath = debrief.recommended_scenario_code === null
    ? null
    : `/operator/simulators/${session.simulator_definition_id}?scenario=${encodeURIComponent(debrief.recommended_scenario_code)}`;

  return (
    <Stack spacing={3}>
      <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2}>
        <Box>
          <Typography component="h1" variant="h4">Итоговый разбор сессии</Typography>
          <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 1 }}>
            <Chip label={session.mode === "exam" ? "Экзамен" : "Тренировка"} />
            <Chip label={result.status === "final" ? "Оценка финальная" : "Оценка предварительная"} color={result.status === "final" ? "success" : "warning"} />
            <Chip label={`Сессия ${session.status}`} />
          </Stack>
        </Box>
        <Button component={RouterLink} to="/operator/simulators" variant="outlined">
          К тренажёрам
        </Button>
      </Stack>

      {session.status === "active" ? (
        <Alert severity="warning">
          Сессия ещё активна. Итоговый разбор может измениться после завершения.
        </Alert>
      ) : null}

      {predictionSummary.count > 0 ? (
        <Alert severity="warning">
          <Typography variant="subtitle2">AI предупредил заранее</Typography>
          <Typography variant="body2">
            Перед {predictionSummary.count} из {result.error_count} ошибок модель заранее отметила повышенный риск.
            {predictionSummary.maxRisk === null
              ? ""
              : ` Максимальный риск составил ${Math.round(predictionSummary.maxRisk * 100)}%.`}
            {predictionSummary.leadMs === null
              ? ""
              : ` Предупреждение появилось за ${formatDurationMs(predictionSummary.leadMs)} до фактической ошибки.`}
          </Typography>
        </Alert>
      ) : null}

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2.5 }}>
        <Stack spacing={1}>
          <Stack direction="row" justifyContent="space-between" alignItems="baseline">
            <Typography variant="h6">Итоговая оценка</Typography>
            <Typography variant="h4">{formatScore(result.score, result.max_score)}</Typography>
          </Stack>
          <LinearProgress variant="determinate" value={scorePercent} sx={{ height: 10, borderRadius: 5 }} />
          <Typography color="text.secondary">{debrief.headline}</Typography>
        </Stack>
      </Paper>

      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(4, 1fr)" } }}>
        <MetricCard label="Количество ошибок" value={String(result.error_count)} />
        <MetricCard label="Критические ошибки" value={String(result.critical_error_count)} />
        <MetricCard label="Среднее время реакции" value={formatDurationMs(result.reaction_time_ms)} />
        <MetricCard
          label="Риск замечен заранее"
          value={`${predictionSummary.count} из ${result.error_count}`}
          helper="ML-предупреждение сработало до ошибки в пределах горизонта модели"
        />
      </Box>

      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
        <MetricCard label="Последовательность" value={`${Math.round(result.sequence_score)} / 100`} />
        <MetricCard label="Скорость реакции" value={`${Math.round(result.reaction_score)} / 100`} />
        <MetricCard label="Безопасность" value={`${Math.round(result.safety_score)} / 100`} />
      </Box>

      <Box>
        <Typography variant="h5" sx={{ mb: 1.5 }}>Timeline ключевых событий</Typography>
        <Alert severity="info" sx={{ mb: 2 }}>
          Прогнозы ML и фактические ошибки показаны на одной временной шкале. Сработавшее предупреждение отмечено отдельно как «AI предупредил».
        </Alert>
        <TrainingTimeline timeline={timeline} errors={errors} />
      </Box>

      <Box>
        <Typography variant="h5" sx={{ mb: 1.5 }}>Ошибки с объяснениями</Typography>
        {errors.length === 0 ? (
          <Alert severity="success">Классифицированных ошибок не обнаружено.</Alert>
        ) : (
          <Stack spacing={1.5}>
            {errors.map((error) => (
              <Paper key={error.id} elevation={0} sx={{ border: "1px solid", borderColor: error.severity === "critical" ? "error.light" : "divider", p: 2 }}>
                <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
                  <Box>
                    <Typography variant="subtitle1">{operatorErrorLabel(error.error_type)}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      {describeOperatorError(error)}
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={1} alignItems="flex-start">
                    <Chip size="small" label={error.severity} color={error.severity === "critical" ? "error" : "warning"} />
                    <Chip size="small" label={error.source === "ml" ? "ML" : "Правило"} />
                  </Stack>
                </Stack>
                {error.causal_chain.length > 0 ? (
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                    Причинная цепочка содержит {error.causal_chain.length} связей и сохранена в результате оценки.
                  </Typography>
                ) : null}
              </Paper>
            ))}
          </Stack>
        )}
      </Box>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2.5 }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
            <Typography variant="h5">Интеллектуальный debrief</Typography>
            <Chip
              label={debrief.generated_by === "rules" ? "Детерминированный разбор" : `AI: ${debrief.generated_by}`}
              color={debrief.generated_by === "rules" ? "default" : "secondary"}
            />
          </Stack>
          <Typography>{debrief.headline}</Typography>
          <Divider />
          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "repeat(2, 1fr)" } }}>
            <Box>
              <Typography variant="subtitle1">Сильные стороны</Typography>
              <Stack component="ul" spacing={0.5} sx={{ pl: 2.5, mb: 0 }}>
                {debrief.strengths.map((item) => <Typography component="li" key={item}>{item}</Typography>)}
              </Stack>
            </Box>
            <Box>
              <Typography variant="subtitle1">Что улучшить</Typography>
              <Stack component="ul" spacing={0.5} sx={{ pl: 2.5, mb: 0 }}>
                {debrief.recommendations.map((item) => <Typography component="li" key={item}>{item}</Typography>)}
              </Stack>
            </Box>
          </Box>
        </Stack>
      </Paper>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "primary.light", p: 2.5 }}>
        <Stack spacing={1.5} alignItems="flex-start">
          <Typography variant="overline" color="primary">Рекомендованная следующая тренировка</Typography>
          <Typography variant="h6">{nextTraining}</Typography>
          {debrief.recommended_scenario_code === null ? (
            <Typography variant="body2" color="text.secondary">
              Для выявленного фокуса пока нет подходящего активного сценария. Рекомендация остаётся учебным направлением и не подменяется frontend-хардкодом.
            </Typography>
          ) : (
            <>
              <Chip label={debrief.recommended_scenario_code} size="small" />
              <Typography variant="body2" color="text.secondary">
                Конкретный сценарий выбран backend из активных сценариев по профилю ошибок. LLM может объяснять рекомендацию, но не выбирает сценарий.
              </Typography>
              <Button component={RouterLink} to={recommendedScenarioPath ?? "/operator/simulators"} variant="contained">
                Перейти к рекомендованной тренировке
              </Button>
            </>
          )}
        </Stack>
      </Paper>
    </Stack>
  );
}
