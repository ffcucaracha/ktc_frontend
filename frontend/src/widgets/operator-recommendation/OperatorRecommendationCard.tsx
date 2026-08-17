import { Alert, Chip, Paper, Stack, Typography } from "@mui/material";

import type { TrainingRecommendationsResponse } from "../../entities/training/api/types";

interface OperatorRecommendationCardProps {
  data: TrainingRecommendationsResponse;
}

export function OperatorRecommendationCard({ data }: OperatorRecommendationCardProps): JSX.Element {
  const recommendation = [...data.items].sort((a, b) => b.priority - a.priority)[0];

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
            <Typography variant="body2" color="text.secondary">
              Приоритет: {recommendation.priority}. Конкретный scenario_code будет подключён, когда backend начнёт возвращать выбранный сценарий; интерфейс не подменяет его локальным хардкодом.
            </Typography>
          </>
        )}
      </Stack>
    </Paper>
  );
}
