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
import { OilHeatingScheme } from "./OilHeatingScheme";
import { useOilHeatingRuntime } from "./model/useOilHeatingRuntime";

interface OilHeatingSimulatorProps {
  session: SimulationSession;
  initialState: SimulationState;
  onStop: () => void;
  stopping: boolean;
}

function connectionStatusLabel(status: string): string {
  if (status === "connected") {
    return "KTC подключен";
  }
  return "KTC недоступен";
}

export function OilHeatingSimulator({
  session,
  initialState,
  onStop,
  stopping,
}: OilHeatingSimulatorProps): JSX.Element {
  const runtime = useOilHeatingRuntime(session.id, initialState);

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
            Подогрев сырой нефти перед ЭЛОУ
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
        <OilHeatingScheme
          state={runtime.state}
          onPumpCommand={(equipmentId, action) => void runtime.sendPumpCommand(equipmentId, action)}
          onRegulatorCommand={runtime.sendRegulatorCommand}
          isCommandPending={runtime.isCommandPending}
          isRegulatorCommandPending={runtime.isRegulatorCommandPending}
        />
      </Paper>
    </Stack>
  );
}
