import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

import type { SimulationSession, SimulationState } from "../../entities/simulation/api/types";
import { formatSessionStatus } from "../../entities/simulation/lib/format";
import { BoilerScheme } from "./BoilerScheme";
import { useBoilerRuntime } from "./model/useBoilerRuntime";

interface BoilerSimulatorProps {
  session: SimulationSession;
  initialState: SimulationState;
  onStop: () => void;
  stopping: boolean;
}

function connectionStatusLabel(status: string): string {
  if (status === "connected") {
    return "WebSocket подключён";
  }
  if (status === "reconnecting") {
    return "WebSocket переподключается";
  }
  if (status === "connecting") {
    return "WebSocket подключается";
  }
  return "WebSocket отключён";
}

export function BoilerSimulator({
  session,
  initialState,
  onStop,
  stopping,
}: BoilerSimulatorProps): JSX.Element {
  const runtime = useBoilerRuntime(session.id, initialState);

  return (
    <Stack spacing={3}>
      <Stack
        alignItems={{ xs: "flex-start", md: "center" }}
        direction={{ xs: "column", md: "row" }}
        justifyContent="space-between"
        spacing={2}
      >
        <Box>
          <Typography component="h2" variant="h4">
            Сессия тренировки
          </Typography>
          <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 1 }}>
            <Chip label={formatSessionStatus(session.status)} color={session.status === "active" ? "success" : "default"} />
            <Chip label={connectionStatusLabel(runtime.connectionStatus)} />
            <Chip label={`Revision: ${runtime.state?.revision ?? "нет данных"}`} />
          </Stack>
        </Box>
        <Button variant="outlined" color="error" onClick={onStop} disabled={stopping}>
          {stopping ? "Завершаем" : "Завершить сессию"}
        </Button>
      </Stack>

      {runtime.errors.map((error) => (
        <Alert severity="error" key={error}>
          {error}
        </Alert>
      ))}

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2 }}>
        <BoilerScheme
          state={runtime.state}
          onCommand={(equipmentId, action) => void runtime.sendPumpCommand(equipmentId, action)}
          isCommandPending={runtime.isCommandPending}
        />
      </Paper>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2 }}>
        <Typography component="h3" variant="h6" sx={{ mb: 1 }}>
          Alarms
        </Typography>
        {runtime.state?.alarms.filter((alarm) => alarm.active).length ? (
          <Stack spacing={1}>
            {runtime.state.alarms
              .filter((alarm) => alarm.active)
              .map((alarm) => (
                <Alert severity={alarm.severity === "critical" ? "error" : "warning"} key={alarm.code}>
                  {alarm.message}
                </Alert>
              ))}
          </Stack>
        ) : (
          <Typography color="text.secondary">Активных аварий нет</Typography>
        )}
      </Paper>
    </Stack>
  );
}
