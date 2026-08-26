import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Slider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import type { SimulationSession, SimulationState } from "../../entities/simulation/api/types";
import { formatSessionStatus } from "../../entities/simulation/lib/format";
import { InstructionDialog } from "../../shared/ui/InstructionDialog";
import { AiCoachPanel } from "../ai-coach/AiCoachPanel";
import instructionText from "./instructions/oil-heating-elou.md?raw";
import { OilHeatingScheme } from "../oil-heating-simulator/OilHeatingScheme";
import { useOilHeatingRuntime } from "../oil-heating-simulator/model/useOilHeatingRuntime";
import type {
  ElouRegulatorId,
  ElouValveId,
  OilDosingAction,
  OilPumpAction,
  OilValveAction,
} from "../oil-heating-simulator/model/useOilHeatingRuntime";

interface OilHeatingElouSimulatorProps {
  session: SimulationSession;
  initialState: SimulationState;
  onStop: () => void;
  stopping: boolean;
}

interface ElouPanelProps {
  state: SimulationState | null;
  onPumpCommand: (equipmentId: "ND2" | "H3", action: OilPumpAction) => void;
  onValveCommand: (equipmentId: ElouValveId, action: OilValveAction) => void;
  onRegulatorCommand: (equipmentId: ElouRegulatorId, value: number) => Promise<void>;
  onDosingCommand: (action: OilDosingAction, value?: number) => Promise<void>;
  onVoltageCommand: () => Promise<void>;
  isPumpPending: (equipmentId: "ND2" | "H3", action: OilPumpAction) => boolean;
  isValvePending: (equipmentId: ElouValveId, action: OilValveAction) => boolean;
  isRegulatorPending: (equipmentId: ElouRegulatorId) => boolean;
  isDosingPending: (action: OilDosingAction) => boolean;
  isVoltagePending: () => boolean;
}

const elouRegulators: Array<{ id: ElouRegulatorId; label: string; unit: string }> = [
  { id: "FRC407", label: "Вход нефти", unit: "%" },
  { id: "FRC408", label: "Подача воды", unit: "%" },
];

const elouValves: ElouValveId[] = ["KR7", "KR8"];

function connectionStatusLabel(status: string): string {
  if (status === "connected") {
    return "KTC подключен";
  }
  return "KTC недоступен";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function elouSection(state: SimulationState | null): Record<string, unknown> {
  const process = state?.process;
  if (!isRecord(process) || !isRecord(process.elou)) {
    return {};
  }
  return process.elou;
}

function elouNumber(state: SimulationState | null, key: string): number | null {
  return readNumber(elouSection(state)[key]);
}

function elouBoolean(state: SimulationState | null, key: string): boolean | null {
  return readBoolean(elouSection(state)[key]);
}

function elouText(state: SimulationState | null, key: string): string | null {
  const value = elouSection(state)[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function formatNumber(value: number | null, digits = 1): string {
  return value === null ? "--" : value.toFixed(digits);
}

function booleanLabel(value: boolean | null, enabled: string, disabled: string): string {
  if (value === null) {
    return "--";
  }
  return value ? enabled : disabled;
}

function ElouPanel({
  state,
  onPumpCommand,
  onValveCommand,
  onRegulatorCommand,
  onDosingCommand,
  onVoltageCommand,
  isPumpPending,
  isValvePending,
  isRegulatorPending,
  isDosingPending,
  isVoltagePending,
}: ElouPanelProps): JSX.Element {
  const [draftRegulators, setDraftRegulators] = useState<Record<ElouRegulatorId, number>>({
    FRC407: 0,
    FRC408: 0,
  });
  const [draftNd2Flow, setDraftNd2Flow] = useState(45);

  const nd2Running = elouBoolean(state, "ND2") === true;
  const h3Running = elouBoolean(state, "H3") === true;
  const e1Voltage = elouBoolean(state, "E1_voltage") === true;
  const processStopped = elouBoolean(state, "process_stopped") === true;
  const stopReason = elouText(state, "stop_reason");

  useEffect(() => {
    setDraftRegulators({
      FRC407: elouNumber(state, "FRC407_valve") ?? 0,
      FRC408: elouNumber(state, "FRC408_valve") ?? 0,
    });
    setDraftNd2Flow(elouNumber(state, "ND2_flow") ?? 45);
  }, [state]);

  return (
    <Stack spacing={1.5}>
      {processStopped ? (
        <Alert severity="error">{stopReason ?? "Блок ЭЛОУ остановлен."}</Alert>
      ) : null}
      <Box
        sx={{
          display: "grid",
          gap: 1.5,
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" },
        }}
      >
        <Metric label="FQR118" value={`${formatNumber(elouNumber(state, "FQR118"))} м3/ч`} />
        <Metric label="E1" value={`${formatNumber(elouNumber(state, "E1_level"))}%`} />
        <Metric label="PO-1" value={`${formatNumber(elouNumber(state, "PO1_level"))}%`} />
        <Metric label="FQR119-1" value={`${formatNumber(elouNumber(state, "FQR119_1"))} м3/ч`} />
      </Box>
      <Box
        sx={{
          display: "grid",
          gap: 1.5,
          gridTemplateColumns: { xs: "1fr", lg: "repeat(2, minmax(0, 1fr))" },
        }}
      >
        {elouRegulators.map((regulator) => {
          const value = Math.round(draftRegulators[regulator.id]);
          const current = elouNumber(state, `${regulator.id}_valve`);
          return (
            <Box
              key={regulator.id}
              sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1, p: 1.5 }}
            >
              <Stack direction="row" justifyContent="space-between" spacing={1}>
                <Box>
                  <Typography fontWeight={700} variant="body2">
                    {regulator.id}
                  </Typography>
                  <Typography color="text.secondary" variant="caption">
                    {regulator.label}: {formatNumber(current, 0)}
                    {regulator.unit}
                  </Typography>
                </Box>
                <Button
                  disabled={state === null || isRegulatorPending(regulator.id)}
                  onClick={() => void onRegulatorCommand(regulator.id, value)}
                  size="small"
                  variant="contained"
                >
                  Применить
                </Button>
              </Stack>
              <Slider
                aria-label={`${regulator.id} valve`}
                disabled={state === null || isRegulatorPending(regulator.id)}
                marks={[
                  { value: 0, label: "0%" },
                  { value: 50, label: "50%" },
                  { value: 100, label: "100%" },
                ]}
                max={100}
                min={0}
                onChange={(_, nextValue) => {
                  setDraftRegulators((currentDraft) => ({
                    ...currentDraft,
                    [regulator.id]: Array.isArray(nextValue) ? nextValue[0] : nextValue,
                  }));
                }}
                step={1}
                sx={{ mt: 1.5 }}
                value={value}
                valueLabelDisplay="auto"
              />
            </Box>
          );
        })}
      </Box>
      <Box
        sx={{
          alignItems: "center",
          border: "1px solid",
          borderColor: elouBoolean(state, "ND2_error") ? "warning.main" : "divider",
          borderRadius: 1,
          display: "grid",
          gap: 1.5,
          gridTemplateColumns: { xs: "1fr", sm: "1fr 150px 130px 130px" },
          p: 1.5,
        }}
      >
        <Box>
          <Typography fontWeight={700} variant="body2">
            Дозатор ND2
          </Typography>
          <Typography color="text.secondary" variant="caption">
            {booleanLabel(nd2Running, "включен", "выключен")}, расход{" "}
            {formatNumber(elouNumber(state, "ND2_flow"))} г/т
          </Typography>
        </Box>
        <TextField
          inputProps={{ min: 0, max: 100, step: 1 }}
          label="Щелочь, г/т"
          onChange={(event) => setDraftNd2Flow(Number(event.target.value))}
          size="small"
          type="number"
          value={draftNd2Flow}
        />
        <Button
          disabled={state === null || isDosingPending("set")}
          onClick={() => void onDosingCommand("set", draftNd2Flow)}
          variant="contained"
        >
          Задать
        </Button>
        <Button
          color={nd2Running ? "error" : "success"}
          disabled={state === null || isDosingPending(nd2Running ? "stop" : "start")}
          onClick={() => void onDosingCommand(nd2Running ? "stop" : "start")}
          variant="outlined"
        >
          {nd2Running ? "Останов" : "Пуск"}
        </Button>
      </Box>
      <Box
        sx={{
          display: "grid",
          gap: 1,
          gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", md: "repeat(5, minmax(0, 1fr))" },
        }}
      >
        <Button
          color={h3Running ? "error" : "success"}
          disabled={state === null || isPumpPending("H3", h3Running ? "stop" : "start")}
          onClick={() => onPumpCommand("H3", h3Running ? "stop" : "start")}
          variant="outlined"
        >
          H3 {h3Running ? "останов" : "пуск"}
        </Button>
        {elouValves.map((valveId) => {
          const opened = elouBoolean(state, valveId);
          const action: OilValveAction = opened ? "close" : "open";
          return (
            <Button
              key={valveId}
              color={opened ? "success" : "inherit"}
              disabled={opened === null || isValvePending(valveId, action)}
              onClick={() => onValveCommand(valveId, action)}
              variant={opened ? "contained" : "outlined"}
            >
              {valveId} {opened ? "открыт" : "закрыт"}
            </Button>
          );
        })}
        <Button
          color={e1Voltage ? "success" : "primary"}
          disabled={state === null || e1Voltage || isVoltagePending()}
          onClick={() => void onVoltageCommand()}
          variant={e1Voltage ? "contained" : "outlined"}
        >
          E1 напряжение
        </Button>
      </Box>
      <Typography color="text.secondary" variant="body2">
        Вода: {formatNumber(elouNumber(state, "water_flow"))} м3/ч. Готовность E1:{" "}
        {booleanLabel(elouBoolean(state, "E1_ready"), "готов", "не готов")}.
      </Typography>
    </Stack>
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1, p: 1.5 }}>
      <Typography color="text.secondary" variant="caption">
        {label}
      </Typography>
      <Typography fontWeight={700}>{value}</Typography>
    </Box>
  );
}

export function OilHeatingElouSimulator({
  session,
  initialState,
  onStop,
  stopping,
}: OilHeatingElouSimulatorProps): JSX.Element {
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
            Подогрев сырой нефти + ЭЛОУ
          </Typography>
          <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 1 }}>
            <Chip
              color={session.status === "active" ? "success" : "default"}
              label={formatSessionStatus(session.status)}
            />
            <Chip
              color={session.mode === "exam" ? "warning" : "primary"}
              label={session.mode === "training" ? "Режим обучения" : "Экзамен"}
            />
            <Chip label={connectionStatusLabel(runtime.connectionStatus)} />
            <Chip label={`Revision: ${runtime.state?.revision ?? "нет данных"}`} />
          </Stack>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button onClick={() => setInstructionOpen(true)} variant="outlined">
            Инструкция
          </Button>
          <Button
            disabled={runtime.isResetCommandPending() || session.status !== "active"}
            onClick={() => void runtime.sendResetCommand()}
            variant="outlined"
          >
            Сброс процесса
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
          Экзаменационный режим: AI-прогнозы рассчитываются на backend, но подсказки оператору
          скрыты до завершения сессии.
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
          gridTemplateColumns: isTrainingMode ? { xs: "1fr", xl: "minmax(0, 1fr) 340px" } : "1fr",
          alignItems: "start",
        }}
      >
        <Stack spacing={2} sx={{ minWidth: 0 }}>
          <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2 }}>
            <OilHeatingScheme
              variant="combined"
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
          <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2 }}>
            <Typography component="h3" sx={{ mb: 1.5 }} variant="h5">
              Блок ЭЛОУ
            </Typography>
            <ElouPanel
              state={runtime.state}
              onPumpCommand={(equipmentId, action) => void runtime.sendElouPumpCommand(equipmentId, action)}
              onValveCommand={(equipmentId, action) => void runtime.sendElouValveCommand(equipmentId, action)}
              onRegulatorCommand={runtime.sendElouRegulatorCommand}
              onDosingCommand={runtime.sendElouDosingCommand}
              onVoltageCommand={runtime.sendElouVoltageCommand}
              isPumpPending={runtime.isElouPumpCommandPending}
              isValvePending={runtime.isElouValveCommandPending}
              isRegulatorPending={runtime.isElouRegulatorCommandPending}
              isDosingPending={runtime.isElouDosingCommandPending}
              isVoltagePending={runtime.isElouVoltageCommandPending}
            />
          </Paper>
        </Stack>
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
