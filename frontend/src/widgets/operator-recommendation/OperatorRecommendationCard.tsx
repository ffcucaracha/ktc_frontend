import { Alert, Chip, Paper, Stack, Typography } from "@mui/material";

import type { TrainingRecommendationsResponse } from "../../entities/training/api/types";

interface OperatorRecommendationCardProps {
  data: TrainingRecommendationsResponse;
}

export function OperatorRecommendationCard({ data }: OperatorRecommendationCardProps): JSX.Element {
  const recommendation = [...data.items].sort((a, b) => a.priority - b.priority)[0];

  return (
    <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 3 }}>
      <Stack spacing={2}>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
          <Typography component="h3" variant="h6">Рекомендация следующей тренировки</Typography>
          <Chip label={`Источник: ${data.source}`} size="small" />
        </Stack>
        {recommendation === undefined ? (
          <Alert severity="info">Недостаточно данных для персональной рекомендации.</Alert>
        ) : (
          <>
            <Typography variant="subtitle1">Фокус: {recommendation.focus}</Typography>
            <Typography>{recommendation.reason}</Typography>
            {recommendation.scenario_code === null ? (
              <Alert severity="info">
                Для этого фокуса пока нет подходящего активного сценария в текущем тренажёре.
              </Alert>
            ) : (
              <Stack spacing={0.5}>
                <Typography variant="body2" color="text.secondary">Рекомендованный сценарий</Typography>
                <Typography fontWeight={600}>{recommendation.scenario_name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {recommendation.scenario_code}
                </Typography>
              </Stack>
            )}
            <Typography variant="body2" color="text.secondary">
              Приоритет: {recommendation.priority}. Сценарий выбирается backend из активных сценариев и их assessment metadata; LLM не определяет выбор.
            </Typography>
          </>
        )}
      </Stack>
    </Paper>
  );
}
