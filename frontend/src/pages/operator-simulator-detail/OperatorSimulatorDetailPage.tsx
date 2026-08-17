import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { Link as RouterLink, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  describeSessionFailure,
  describeSimulationError,
} from "../../entities/simulation/lib/format";
import {
  useCreateSimulationSessionMutation,
  useSimulatorQuery,
  useTrainingScenariosQuery,
} from "../../entities/simulation/model/queries";
import type { TrainingSessionMode } from "../../entities/simulation/api/types";
import { ErrorView } from "../../shared/ui/ErrorView";
import { LoadingView } from "../../shared/ui/LoadingView";

export function OperatorSimulatorDetailPage(): JSX.Element {
  const { simulatorId } = useParams();
  const resolvedSimulatorId = simulatorId ?? "";
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedScenarioCode = searchParams.get("scenario");
  const creationInFlightRef = useRef(false);
  const [sessionFailure, setSessionFailure] = useState<string | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [mode, setMode] = useState<TrainingSessionMode>("training");
  const simulatorQuery = useSimulatorQuery(resolvedSimulatorId);
  const scenariosQuery = useTrainingScenariosQuery(resolvedSimulatorId);
  const createSessionMutation = useCreateSimulationSessionMutation();

  useEffect(() => {
    if (selectedScenarioId.length !== 0 || !scenariosQuery.data?.length) {
      return;
    }
    const requestedScenario = requestedScenarioCode
      ? scenariosQuery.data.find((item) => item.code === requestedScenarioCode)
      : undefined;
    setSelectedScenarioId(requestedScenario?.id ?? scenariosQuery.data[0].id);
  }, [requestedScenarioCode, scenariosQuery.data, selectedScenarioId]);

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
  const scenarios = scenariosQuery.data ?? [];
  const selectedScenario = scenarios.find((item) => item.id === selectedScenarioId);
  const createDisabled =
    createSessionMutation.isPending ||
    !simulator.is_active ||
    scenariosQuery.isLoading ||
    (scenarios.length > 0 && selectedScenarioId.length === 0);

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
      {scenariosQuery.isError ? (
        <Alert severity="warning">Не удалось загрузить учебные сценарии.</Alert>
      ) : null}
      {requestedScenarioCode !== null && scenarios.length > 0 && selectedScenario?.code !== requestedScenarioCode ? (
        <Alert severity="info">
          Рекомендованный сценарий больше не активен или не относится к этому тренажёру. Выбран доступный сценарий по умолчанию.
        </Alert>
      ) : null}
      {requestedScenarioCode !== null && selectedScenario?.code === requestedScenarioCode ? (
        <Alert severity="success">
          Персональная рекомендация применена: выбран сценарий «{selectedScenario.name}».
        </Alert>
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
              Выберите сценарий и режим. В экзаменационном режиме дальнейшие AI-подсказки будут
              скрыты, но действия и телеметрия продолжат фиксироваться.
            </Typography>

            <FormControl fullWidth disabled={scenariosQuery.isLoading || scenarios.length === 0}>
              <InputLabel id="training-scenario-label">Учебный сценарий</InputLabel>
              <Select
                labelId="training-scenario-label"
                label="Учебный сценарий"
                value={selectedScenarioId}
                onChange={(event) => setSelectedScenarioId(event.target.value)}
              >
                {scenarios.map((scenario) => (
                  <MenuItem key={scenario.id} value={scenario.id}>
                    {scenario.name} · {scenario.difficulty}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {scenarios.length === 0 && !scenariosQuery.isLoading ? (
              <Alert severity="info">
                Для тренажёра пока нет активных сценариев. Можно запустить свободную тренировку.
              </Alert>
            ) : null}

            {selectedScenario !== undefined ? (
              <Typography color="text.secondary">{selectedScenario.description}</Typography>
            ) : null}

            <FormControl fullWidth>
              <InputLabel id="training-mode-label">Режим</InputLabel>
              <Select
                labelId="training-mode-label"
                label="Режим"
                value={mode}
                onChange={(event) => setMode(event.target.value as TrainingSessionMode)}
              >
                <MenuItem value="training">Тренировка</MenuItem>
                <MenuItem value="exam">Экзамен</MenuItem>
              </Select>
            </FormControl>

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
                  {
                    simulator_id: simulator.id,
                    scenario_id: selectedScenarioId || undefined,
                    mode,
                  },
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
              {createSessionMutation.isPending ? "Создаём сессию" : "Начать"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  );
}
