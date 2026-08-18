import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";

import { describeSimulationError } from "../../entities/simulation/lib/format";
import { useSimulatorsQuery } from "../../entities/simulation/model/queries";
import { formatScore } from "../../entities/training/lib/result";
import { useOperatorTrainingResultsQuery } from "../../entities/training/model/queries";
import { useCurrentUserQuery } from "../../features/auth/model/queries";
import { ErrorView } from "../../shared/ui/ErrorView";
import { LoadingView } from "../../shared/ui/LoadingView";

function formatCompletedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function OperatorSimulatorsPage(): JSX.Element {
  const simulatorsQuery = useSimulatorsQuery();
  const { data: user } = useCurrentUserQuery();
  const historyQuery = useOperatorTrainingResultsQuery(user?.id ?? "");

  if (simulatorsQuery.isLoading) {
    return <LoadingView message="Загружаем тренажёры" />;
  }

  if (simulatorsQuery.isError) {
    return (
      <ErrorView
        message={describeSimulationError(simulatorsQuery.error)}
        actionLabel="Повторить"
        onAction={() => void simulatorsQuery.refetch()}
      />
    );
  }

  const simulators = simulatorsQuery.data ?? [];
  const history = [...(historyQuery.data ?? [])].sort(
    (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
  );

  return (
    <Stack spacing={4}>
      <Stack spacing={3}>
        <Box>
          <Typography component="h2" variant="h4">
            Тренажёры
          </Typography>
          <Typography color="text.secondary">
            Выберите доступную установку для запуска тренировочной сессии.
          </Typography>
        </Box>

        {simulators.length === 0 ? (
          <Alert severity="info">Сейчас нет доступных тренажёров.</Alert>
        ) : (
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            {simulators.map((simulator) => (
              <Card key={simulator.id} variant="outlined" sx={{ flex: 1, maxWidth: 520 }}>
                <CardContent>
                  <Stack spacing={1.5}>
                    <Stack direction="row" justifyContent="space-between" spacing={2}>
                      <Typography component="h3" variant="h5">
                        {simulator.name}
                      </Typography>
                      <Chip
                        label={simulator.is_active ? "Доступен" : "Недоступен"}
                        color={simulator.is_active ? "success" : "default"}
                        size="small"
                      />
                    </Stack>
                    <Typography color="text.secondary">
                      {simulator.description || "Демонстрационная установка для обучения оператора."}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Тип визуализации: {simulator.visualization_type}
                    </Typography>
                  </Stack>
                </CardContent>
                <CardActions>
                  <Button
                    component={RouterLink}
                    to={`/operator/simulators/${simulator.id}`}
                    variant="contained"
                    disabled={!simulator.is_active}
                  >
                    Открыть
                  </Button>
                </CardActions>
              </Card>
            ))}
          </Stack>
        )}
      </Stack>

      <Stack spacing={2}>
        <Box>
          <Typography component="h2" variant="h4">
            История прохождений
          </Typography>
          <Typography color="text.secondary">
            Завершённые тренировки и сохранённые итоговые разборы.
          </Typography>
        </Box>

        {historyQuery.isLoading ? (
          <Typography color="text.secondary">Загружаем историю...</Typography>
        ) : historyQuery.isError ? (
          <Alert
            severity="warning"
            action={(
              <Button color="inherit" size="small" onClick={() => void historyQuery.refetch()}>
                Повторить
              </Button>
            )}
          >
            Не удалось загрузить историю прохождений.
          </Alert>
        ) : history.length === 0 ? (
          <Alert severity="info">Завершённых прохождений пока нет.</Alert>
        ) : (
          <Stack spacing={1.5}>
            {history.map((result) => (
              <Paper
                key={result.id}
                elevation={0}
                sx={{ border: "1px solid", borderColor: "divider", p: 2 }}
              >
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  justifyContent="space-between"
                  alignItems={{ sm: "center" }}
                  spacing={2}
                >
                  <Stack spacing={0.5}>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                      <Typography variant="subtitle1">Тренировочная сессия</Typography>
                      <Chip
                        size="small"
                        label={result.status === "final" ? "Разбор готов" : result.status}
                        color={result.status === "final" ? "success" : "default"}
                      />
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      {formatCompletedAt(result.updated_at || result.created_at)} · оценка {formatScore(result.score, result.max_score)} · ошибок {result.error_count}
                    </Typography>
                  </Stack>
                  <Button
                    component={RouterLink}
                    to={`/operator/sessions/${result.session_id}/result`}
                    variant="outlined"
                  >
                    Открыть разбор
                  </Button>
                </Stack>
              </Paper>
            ))}
          </Stack>
        )}
      </Stack>
    </Stack>
  );
}
