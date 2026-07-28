import { Alert, Button, Stack } from "@mui/material";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";

import { describeSimulationError } from "../../entities/simulation/lib/format";
import {
  useSimulatorQuery,
  useSimulationSessionQuery,
  useSimulationStateQuery,
  useStopSimulationSessionMutation,
} from "../../entities/simulation/model/queries";
import { ErrorView } from "../../shared/ui/ErrorView";
import { LoadingView } from "../../shared/ui/LoadingView";
import { BoilerSimulator } from "../../widgets/boiler-simulator/BoilerSimulator";
import { OilHeatingSimulator } from "../../widgets/oil-heating-simulator/OilHeatingSimulator";

export function OperatorSessionPage(): JSX.Element {
  const { sessionId } = useParams();
  const resolvedSessionId = sessionId ?? "";
  const navigate = useNavigate();
  const sessionQuery = useSimulationSessionQuery(resolvedSessionId);
  const simulatorQuery = useSimulatorQuery(sessionQuery.data?.simulator_definition_id ?? "");
  const stateQuery = useSimulationStateQuery(resolvedSessionId);
  const stopMutation = useStopSimulationSessionMutation();

  if (sessionId === undefined) {
    return <ErrorView title="Сессия не найдена" message="Некорректный адрес страницы." />;
  }

  if (sessionQuery.isLoading || stateQuery.isLoading || simulatorQuery.isLoading) {
    return <LoadingView message="Загружаем сессию и snapshot" />;
  }

  if (sessionQuery.isError || sessionQuery.data === undefined) {
    return (
      <ErrorView
        message={describeSimulationError(sessionQuery.error)}
        actionLabel="К тренажёрам"
        onAction={() => navigate("/operator/simulators")}
      />
    );
  }

  if (simulatorQuery.isError || simulatorQuery.data === undefined) {
    return (
      <ErrorView
        message={describeSimulationError(simulatorQuery.error)}
        actionLabel="К тренажёрам"
        onAction={() => navigate("/operator/simulators")}
      />
    );
  }

  if (stateQuery.isError || stateQuery.data === undefined) {
    return (
      <Stack spacing={2}>
        <Button component={RouterLink} to="/operator/simulators">
          К тренажёрам
        </Button>
        <ErrorView
          message={describeSimulationError(stateQuery.error)}
          actionLabel="Повторить"
          onAction={() => void stateQuery.refetch()}
        />
      </Stack>
    );
  }

  const simulator = simulatorQuery.data;
  const simulatorComponent =
    simulator.visualization_type === "oil-heating-v1" ? (
      <OilHeatingSimulator
        session={sessionQuery.data}
        initialState={stateQuery.data}
        stopping={stopMutation.isPending}
        onStop={() => {
          stopMutation.mutate(sessionQuery.data.id, {
            onSuccess: () => {
              navigate("/operator/simulators");
            },
          });
        }}
      />
    ) : simulator.visualization_type === "boiler-v1" ? (
      <BoilerSimulator
        session={sessionQuery.data}
        initialState={stateQuery.data}
        stopping={stopMutation.isPending}
        onStop={() => {
          stopMutation.mutate(sessionQuery.data.id, {
            onSuccess: () => {
              navigate("/operator/simulators");
            },
          });
        }}
      />
    ) : (
      <ErrorView title="Визуализация не найдена" message="Для тренажёра нет поддерживаемой мнемосхемы." />
    );

  return (
    <Stack spacing={2}>
      {stopMutation.error !== null ? (
        <Alert severity="error">{describeSimulationError(stopMutation.error)}</Alert>
      ) : null}
      {simulatorComponent}
    </Stack>
  );
}
