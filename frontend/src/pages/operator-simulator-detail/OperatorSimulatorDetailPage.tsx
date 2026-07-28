import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
} from "@mui/material";
import { useRef } from "react";
import { useState } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";

import {
  describeSessionFailure,
  describeSimulationError,
} from "../../entities/simulation/lib/format";
import {
  useCreateSimulationSessionMutation,
  useSimulatorQuery,
} from "../../entities/simulation/model/queries";
import { ErrorView } from "../../shared/ui/ErrorView";
import { LoadingView } from "../../shared/ui/LoadingView";

export function OperatorSimulatorDetailPage(): JSX.Element {
  const { simulatorId } = useParams();
  const resolvedSimulatorId = simulatorId ?? "";
  const navigate = useNavigate();
  const creationInFlightRef = useRef(false);
  const [sessionFailure, setSessionFailure] = useState<string | null>(null);
  const simulatorQuery = useSimulatorQuery(resolvedSimulatorId);
  const createSessionMutation = useCreateSimulationSessionMutation();

  if (simulatorId === undefined) {
    return <ErrorView title="Тренажёр не найден" message="Некорректный адрес страницы." />;
  }

  if (simulatorQuery.isLoading) {
    return <LoadingView message="Загружаем тренажёр" />;
  }

  if (simulatorQuery.isError || simulatorQuery.data === undefined) {
    return (
      <ErrorView
        message={describeSimulationError(simulatorQuery.error)}
        actionLabel="К каталогу"
        onAction={() => navigate("/operator/simulators")}
      />
    );
  }

  const simulator = simulatorQuery.data;
  const createDisabled = createSessionMutation.isPending || !simulator.is_active;

  return (
    <Stack spacing={3}>
      <Box>
        <Button component={RouterLink} to="/operator/simulators" sx={{ mb: 1 }}>
          К каталогу
        </Button>
        <Stack
          alignItems={{ xs: "flex-start", sm: "center" }}
          direction={{ xs: "column", sm: "row" }}
          justifyContent="space-between"
          spacing={2}
        >
          <Box>
            <Typography component="h2" variant="h4">
              {simulator.name}
            </Typography>
            <Typography color="text.secondary">{simulator.description}</Typography>
          </Box>
          <Chip
            label={simulator.is_active ? "Доступен" : "Недоступен"}
            color={simulator.is_active ? "success" : "default"}
          />
        </Stack>
      </Box>

      {!simulator.is_active ? (
        <Alert severity="warning">Тренажёр временно недоступен для запуска.</Alert>
      ) : null}
      {sessionFailure !== null ? <Alert severity="error">{sessionFailure}</Alert> : null}
      {createSessionMutation.error !== null ? (
        <Alert severity="error">{describeSimulationError(createSessionMutation.error)}</Alert>
      ) : null}

      <Card variant="outlined">
        <CardContent>
          <Stack spacing={2}>
            <Typography component="h3" variant="h6">
              Подготовка тренировки
            </Typography>
            <Typography color="text.secondary">
              Будет создана локальная сессия тренажёра, затем откроется визуальная мнемосхема.
            </Typography>
            <Button
              variant="contained"
              size="large"
              disabled={createDisabled}
              onClick={() => {
                if (creationInFlightRef.current) {
                  return;
                }
                creationInFlightRef.current = true;
                setSessionFailure(null);
                createSessionMutation.mutate(
                  { simulator_id: simulator.id },
                  {
                    onSuccess: (session) => {
                      if (session.status === "failed") {
                        creationInFlightRef.current = false;
                        setSessionFailure(describeSessionFailure(session.error_code));
                        return;
                      }
                      navigate(`/operator/sessions/${session.id}`);
                    },
                    onError: () => {
                      creationInFlightRef.current = false;
                    },
                  },
                );
              }}
            >
              {createSessionMutation.isPending ? "Создаём сессию" : "Начать тренировку"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  );
}
