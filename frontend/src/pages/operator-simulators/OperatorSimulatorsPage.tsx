import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Stack,
  Typography,
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";

import { describeSimulationError } from "../../entities/simulation/lib/format";
import { useSimulatorsQuery } from "../../entities/simulation/model/queries";
import { ErrorView } from "../../shared/ui/ErrorView";
import { LoadingView } from "../../shared/ui/LoadingView";

export function OperatorSimulatorsPage(): JSX.Element {
  const simulatorsQuery = useSimulatorsQuery();

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

  return (
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
  );
}
