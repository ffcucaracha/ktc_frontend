import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { useState } from "react";

import type { SimulationSession, SimulationState } from "../../entities/simulation/api/types";
import { formatSessionStatus } from "../../entities/simulation/lib/format";
import { InstructionDialog } from "../../shared/ui/InstructionDialog";
import { AiCoachPanel } from "../ai-coach/AiCoachPanel";
import instructionText from "./instructions/oil-heating.md?raw";
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
  const runtimeEnabled = session.status === "active" && !stopping;
  const runtime = useOilHeatingRuntime(session.id, initialState, runtimeEnabled);
  const isTrainingMode = session.mode === "training";
  const [instructionOpen, setInstructionOpen] = useState(false);

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
            <Chip label={session.mode === "training" ? "Режим обучения" : "Экзамен"} color={session.mode === "exam" ? "warning" : "primary"} />
            <Chip label={connectionStatusLabel(runtime.connectionStatus)} />
            <Chip label={`Revision: ${runtime.state?.revision ?? "нет данных"}`} />
          </Stack>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button onClick={() => setInstructionOpen(true)} variant="outlined">
            Инструкция
          </Button>
          <Button
            color="error"
            disabled={stopping || session.status !== "active"}
            onClick={onStop}
            variant="outlined"
          >
            {stopping ? "Завершаем" : "Завершить сессию"}
          </Button>
        </Stack>
      </Stack>

      {session.mode === "exam" ? (
        <Alert severity="info">
          Экзаменационный режим: AI-прогнозы рассчитываются на backend, но подсказки оператору скрыты до завершения сессии.
        </Alert>
      ) : null}

      {runtime.errors.map((error) => (
        <Alert severity="error" key={error}>
          {error}
        </Alert>
      ))}

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: isTrainingMode ? { xs: "1fr", lg: "minmax(0, 1fr) 340px" } : "1fr",
          alignItems: "start",
        }}
      >
        <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2, minWidth: 0 }}>
          <OilHeatingScheme
            state={runtime.state}
            onPumpCommand={(equipmentId, action) => void runtime.sendPumpCommand(equipmentId, action)}
            onValveCommand={(equipmentId, action) => void runtime.sendValveCommand(equipmentId, action)}
            onRegulatorCommand={runtime.sendRegulatorCommand}
            onDosingCommand={runtime.sendDosingCommand}
            onResetCommand={runtime.sendResetCommand}
            isCommandPending={runtime.isCommandPending}
            isValveCommandPending={runtime.isValveCommandPending}
            isRegulatorCommandPending={runtime.isRegulatorCommandPending}
            isDosingCommandPending={runtime.isDosingCommandPending}
            isResetCommandPending={runtime.isResetCommandPending}
          />
        </Paper>
        {isTrainingMode ? <AiCoachPanel sessionId={session.id} /> : null}
      </Box>
      <InstructionDialog
        content={instructionText}
        onClose={() => setInstructionOpen(false)}
        open={instructionOpen}
        title="Инструкция по тренажёру"
      />
    </Stack>
  );
}
