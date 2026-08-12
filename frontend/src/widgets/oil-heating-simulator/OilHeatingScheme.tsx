import { useEffect, useRef, useState } from "react";
import { Box, Button, Slider, Stack, Typography } from "@mui/material";

import type { SimulationState } from "../../entities/simulation/api/types";
import type { OilPumpAction, OilPumpId, OilRegulatorId } from "./model/useOilHeatingRuntime";

interface OilHeatingSchemeProps {
  state: SimulationState | null;
  onPumpCommand: (equipmentId: OilPumpId, action: OilPumpAction) => void;
  onRegulatorCommand: (equipmentId: OilRegulatorId, value: number) => Promise<void>;
  isCommandPending: (equipmentId: OilPumpId, action: OilPumpAction) => boolean;
  isRegulatorCommandPending: (equipmentId: OilRegulatorId) => boolean;
}

interface PumpPosition {
  id: OilPumpId;
  x: number;
  y: number;
  buttonLeft: string;
  buttonTop: string;
}

interface RegulatorLine {
  y: number;
  id: OilRegulatorId;
  label: string;
  exchangers: string;
}

const pumps: PumpPosition[] = [
  { id: "H1A", x: 120, y: 95, buttonLeft: "11.5%", buttonTop: "25%" },
  { id: "H1B", x: 120, y: 185, buttonLeft: "11.5%", buttonTop: "49%" },
  { id: "H1V", x: 120, y: 275, buttonLeft: "11.5%", buttonTop: "72.5%" },
];

const regulatorLines: RegulatorLine[] = [
  { y: 75, id: "FRC404", label: "FRC 404", exchangers: "Т-2 ... Т-1/1" },
  { y: 185, id: "FRC405", label: "FRC 405", exchangers: "Т-4/1 ... Т-7/1" },
  { y: 295, id: "FRC406", label: "FRC 406", exchangers: "Т-7/2 ... Т-11" },
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readRecord(value: unknown, key: string): Record<string, unknown> {
  if (!isRecord(value)) {
    return {};
  }
  const nested = value[key];
  return isRecord(nested) ? nested : {};
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function processSection(state: SimulationState | null, key: string): Record<string, unknown> {
  return readRecord(state?.process, key);
}

function sensorValue(state: SimulationState | null, key: string): number | null {
  return readNumber(processSection(state, "sensors")[key]);
}

function regulatorValue(state: SimulationState | null, regulatorId: OilRegulatorId): number | null {
  return readNumber(readRecord(processSection(state, "regulators"), regulatorId).valve);
}

function outputValue(state: SimulationState | null, key: string): number | null {
  return readNumber(processSection(state, "installation_output")[key]);
}

function formatNumber(value: number | null, digits = 1): string {
  return value === null ? "--" : value.toFixed(digits);
}

function formatRawValue(value: unknown): string {
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toString() : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  }
  if (typeof value === "string") {
    return value;
  }
  if (isRecord(value)) {
    return Object.entries(value)
      .map(([key, nestedValue]) => `${key}: ${formatRawValue(nestedValue)}`)
      .join(", ");
  }
  return "--";
}

function processRows(state: SimulationState | null): Array<{ label: string; value: string }> {
  if (!isRecord(state?.process)) {
    return [];
  }
  return Object.entries(state.process).flatMap(([sectionName, sectionValue]) => {
    if (!isRecord(sectionValue)) {
      return [{ label: sectionName, value: formatRawValue(sectionValue) }];
    }
    return Object.entries(sectionValue).map(([key, value]) => ({
      label: `${sectionName}.${key}`,
      value: formatRawValue(value),
    }));
  });
}

function pumpColor(status: string | undefined): string {
  if (status === "running") {
    return "#1b5e20";
  }
  if (status === "fault" || status === "unavailable") {
    return "#b71c1c";
  }
  return "#546e7a";
}

function pumpStatus(state: SimulationState | null, pumpId: OilPumpId): string {
  return state?.equipment[pumpId]?.status ?? "нет данных";
}

function pumpFlow(state: SimulationState | null, pumpId: OilPumpId): number {
  return state?.equipment[pumpId]?.flow_kg_h ?? 0;
}

interface PumpActionButtonProps {
  pumpId: OilPumpId;
  status: string | undefined;
  left: string;
  top: string;
  onCommand: (equipmentId: OilPumpId, action: OilPumpAction) => void;
  isCommandPending: (equipmentId: OilPumpId, action: OilPumpAction) => boolean;
}

function PumpActionButton({
  pumpId,
  status,
  left,
  top,
  onCommand,
  isCommandPending,
}: PumpActionButtonProps): JSX.Element {
  const action: OilPumpAction = status === "running" ? "stop" : "start";
  const label = action === "stop" ? "Стоп" : "Пуск";
  const pumpLabel = `Н-${pumpId.slice(1)}`;

  return (
    <Button
      variant="contained"
      aria-label={`${label} ${pumpId}`}
      onClick={() => onCommand(pumpId, action)}
      disabled={status === undefined || isCommandPending(pumpId, action)}
      sx={{
        bgcolor: action === "stop" ? "error.main" : "success.dark",
        border: "5px solid",
        borderColor: "background.paper",
        borderRadius: "50%",
        boxShadow: 3,
        color: "common.white",
        flexDirection: "column",
        fontSize: { xs: 10, sm: 11 },
        fontWeight: 700,
        height: { xs: 58, sm: 66 },
        lineHeight: 1.05,
        left,
        minWidth: 0,
        p: 0,
        position: "absolute",
        top,
        transform: "translate(-50%, -50%)",
        width: { xs: 58, sm: 66 },
        "&:hover": {
          bgcolor: action === "stop" ? "error.dark" : "success.main",
        },
      }}
    >
      <Box component="span" sx={{ display: "block" }}>
        {pumpLabel}
      </Box>
      <Box component="span" sx={{ display: "block", fontSize: { xs: 11, sm: 12 }, mt: 0.25 }}>
        {label}
      </Box>
    </Button>
  );
}

interface RegulatorControlProps {
  line: RegulatorLine;
  state: SimulationState | null;
  value: number;
  onStartEdit: (equipmentId: OilRegulatorId) => void;
  onChange: (equipmentId: OilRegulatorId, value: number) => void;
  onApply: (equipmentId: OilRegulatorId, value: number) => void;
  pending: boolean;
}

function RegulatorControl({
  line,
  state,
  value,
  onStartEdit,
  onChange,
  onApply,
  pending,
}: RegulatorControlProps): JSX.Element {
  const currentValue = regulatorValue(state, line.id);
  const normalizedValue = Math.round(value);
  const changed = currentValue === null || normalizedValue !== Math.round(currentValue);

  return (
    <Box
      data-testid={`regulator-${line.id}`}
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        minWidth: 0,
        p: 1.5,
      }}
    >
      <Stack alignItems="center" direction="row" justifyContent="space-between" spacing={1}>
        <Box sx={{ minWidth: 0 }}>
          <Typography fontWeight={700} variant="body2">
            {line.label}
          </Typography>
          <Typography color="text.secondary" variant="caption">
            клапан {formatNumber(currentValue, 0)}%
          </Typography>
        </Box>
        <Button
          size="small"
          variant="contained"
          onClick={() => onApply(line.id, normalizedValue)}
          disabled={state === null || pending || !changed}
          sx={{ minWidth: 96 }}
        >
          {pending ? "Ждём" : "Применить"}
        </Button>
      </Stack>
      <Slider
        aria-label={`${line.id} valve`}
        value={normalizedValue}
        min={0}
        max={100}
        step={1}
        marks={[
          { value: 0, label: "0%" },
          { value: 50, label: "50%" },
          { value: 100, label: "100%" },
        ]}
        valueLabelDisplay="auto"
        disabled={state === null || pending}
        onFocus={() => onStartEdit(line.id)}
        onPointerDown={() => onStartEdit(line.id)}
        onChange={(_, nextValue) => {
          onChange(line.id, Array.isArray(nextValue) ? nextValue[0] : nextValue);
        }}
        sx={{ mt: 1.5 }}
      />
    </Box>
  );
}

export function OilHeatingScheme({
  state,
  onPumpCommand,
  onRegulatorCommand,
  isCommandPending,
  isRegulatorCommandPending,
}: OilHeatingSchemeProps): JSX.Element {
  const [draftRegulators, setDraftRegulators] = useState<Record<OilRegulatorId, number>>({
    FRC404: 0,
    FRC405: 0,
    FRC406: 0,
  });
  const dirtyRegulatorsRef = useRef<Record<OilRegulatorId, boolean>>({
    FRC404: false,
    FRC405: false,
    FRC406: false,
  });
  const totalFlow = pumps.reduce((sum, pump) => sum + pumpFlow(state, pump.id), 0);
  const temperature = state?.boiler.temperature_c;
  const pressure = state?.boiler.pressure_bar;
  const inletTemperature = sensorValue(state, "TR5K3T");
  const density = sensorValue(state, "QR5K3D");
  const pumpOutletFlow = sensorValue(state, "FYQR117");
  const ktcPressure = sensorValue(state, "PRA351");
  const outputFlow = outputValue(state, "oil_flow_exit");
  const rawRows = processRows(state);

  useEffect(() => {
    setDraftRegulators((current) => {
      const next = { ...current };
      for (const line of regulatorLines) {
        const value = regulatorValue(state, line.id);
        if (value !== null && !dirtyRegulatorsRef.current[line.id] && !isRegulatorCommandPending(line.id)) {
          next[line.id] = value;
        }
      }
      return next;
    });
  }, [isRegulatorCommandPending, state]);

  const startEditRegulator = (equipmentId: OilRegulatorId): void => {
    dirtyRegulatorsRef.current[equipmentId] = true;
  };

  const updateDraftRegulator = (equipmentId: OilRegulatorId, value: number): void => {
    dirtyRegulatorsRef.current[equipmentId] = true;
    setDraftRegulators((current) => ({
      ...current,
      [equipmentId]: Math.min(100, Math.max(0, Math.round(value))),
    }));
  };

  const applyDraftRegulator = (equipmentId: OilRegulatorId, value: number): void => {
    void onRegulatorCommand(equipmentId, value).finally(() => {
      dirtyRegulatorsRef.current[equipmentId] = false;
    });
  };

  return (
    <Box>
      <Box sx={{ position: "relative" }}>
        <svg
          role="img"
          aria-labelledby="oil-heating-title oil-heating-desc"
          viewBox="0 0 1040 380"
          width="100%"
          style={{ maxHeight: 460 }}
        >
          <title id="oil-heating-title">Мнемосхема подогрева сырой нефти перед ЭЛОУ</title>
          <desc id="oil-heating-desc">
            Три сырьевых насоса, общий коллектор, регуляторы расхода и ветки теплообменников.
          </desc>
          <rect x="0" y="0" width="1040" height="380" rx="8" fill="#f7faf8" />

          <line x1="190" y1="185" x2="300" y2="185" stroke="#607d8b" strokeWidth="16" />
          <line x1="300" y1="75" x2="300" y2="295" stroke="#607d8b" strokeWidth="16" />
          <line x1="300" y1="75" x2="760" y2="75" stroke="#90a4ae" strokeWidth="12" />
          <line x1="300" y1="185" x2="760" y2="185" stroke="#90a4ae" strokeWidth="12" />
          <line x1="300" y1="295" x2="760" y2="295" stroke="#90a4ae" strokeWidth="12" />
          <line x1="760" y1="75" x2="760" y2="295" stroke="#607d8b" strokeWidth="16" />
          <line x1="760" y1="185" x2="1000" y2="185" stroke="#607d8b" strokeWidth="16" />

          {pumps.map((pump) => {
            const status = pumpStatus(state, pump.id);
            return (
              <g key={pump.id} aria-label={`Насос ${pump.id}: ${status}`}>
                <line x1={pump.x + 45} y1={pump.y} x2="300" y2={pump.y} stroke="#607d8b" strokeWidth="10" />
                <circle cx={pump.x} cy={pump.y} r="38" fill={pumpColor(status)} />
                <circle cx={pump.x} cy={pump.y} r="21" fill="#ffffff" opacity="0.86" />
              </g>
            );
          })}

          {regulatorLines.map((line) => {
            const valve = regulatorValue(state, line.id);
            const capacity = valve === null ? null : 450 * valve / 100;
            return (
              <g key={line.label}>
                <rect x="350" y={line.y - 35} width="104" height="70" rx="6" fill="#e8f5e9" stroke="#2e7d32" />
                <text x="402" y={line.y - 12} textAnchor="middle" fontSize="15" fill="#1b5e20">
                  {line.label}
                </text>
                <text x="402" y={line.y + 8} textAnchor="middle" fontSize="12" fill="#1b5e20">
                  до {formatNumber(capacity)} м3/ч
                </text>
                <text x="402" y={line.y + 25} textAnchor="middle" fontSize="12" fill="#1b5e20">
                  клапан {formatNumber(valve, 0)}%
                </text>
                <rect x="520" y={line.y - 32} width="170" height="64" rx="8" fill="#fff8e1" stroke="#9e7d19" />
                <text x="605" y={line.y - 7} textAnchor="middle" fontSize="14" fill="#5d4b00">
                  Теплообменники
                </text>
                <text x="605" y={line.y + 16} textAnchor="middle" fontSize="15" fill="#5d4b00">
                  {line.exchangers}
                </text>
              </g>
            );
          })}

          <g aria-label="Показатели коллектора">
            <rect x="800" y="122" width="220" height="126" rx="8" fill="#ffffff" stroke="#cfd8dc" />
            <text x="910" y="152" textAnchor="middle" fontSize="17" fill="#263238">
              Коллектор перед ЭЛОУ
            </text>
            <text x="910" y="181" textAnchor="middle" fontSize="15" fill="#455a64">
              {temperature === undefined ? "TR41-1: --" : `TR41-1: ${temperature.toFixed(1)} C`}
            </text>
            <text x="910" y="206" textAnchor="middle" fontSize="15" fill="#455a64">
              {pressure === undefined ? "PRA351: --" : `PRA351: ${pressure.toFixed(1)} bar`}
            </text>
            <text x="910" y="230" textAnchor="middle" fontSize="13" fill="#607d8b">
              KTC PRA351: {formatNumber(ktcPressure)} кгс/см2
            </text>
            <text x="910" y="246" textAnchor="middle" fontSize="13" fill="#607d8b">
              Выход: {formatNumber(outputFlow)} м3/ч
            </text>
          </g>
        </svg>
        {pumps.map((pump) => (
          <PumpActionButton
            key={pump.id}
            pumpId={pump.id}
            status={state?.equipment[pump.id]?.status}
            left={pump.buttonLeft}
            top={pump.buttonTop}
            onCommand={onPumpCommand}
            isCommandPending={isCommandPending}
          />
        ))}
      </Box>

      <Stack spacing={1.5} sx={{ mt: 1.5 }}>
        <Typography color="text.secondary" variant="body2">
          После насосов: {formatNumber(pumpOutletFlow)} м3/ч ({totalFlow.toFixed(1)} т/ч).
          Выход блока: {formatNumber(outputFlow)} м3/ч. Входная температура: {formatNumber(inletTemperature)} C.
          Плотность: {formatNumber(density, 3)} г/см3.
        </Typography>
        <Box
          sx={{
            display: "grid",
            gap: 1.5,
            gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" },
          }}
        >
          {regulatorLines.map((line) => (
            <RegulatorControl
              key={line.id}
              line={line}
              state={state}
              value={draftRegulators[line.id]}
              onStartEdit={startEditRegulator}
              onChange={updateDraftRegulator}
              onApply={applyDraftRegulator}
              pending={isRegulatorCommandPending(line.id)}
            />
          ))}
        </Box>
        {rawRows.length > 0 && (
          <Box
            sx={{
              borderTop: "1px solid",
              borderColor: "divider",
              display: "grid",
              gap: 1,
              gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(3, minmax(0, 1fr))" },
              pt: 1.5,
            }}
          >
            {rawRows.map((row) => (
              <Box key={row.label} sx={{ minWidth: 0 }}>
                <Typography color="text.secondary" variant="caption">
                  {row.label}
                </Typography>
                <Typography sx={{ overflowWrap: "anywhere" }} variant="body2">
                  {row.value}
                </Typography>
              </Box>
            ))}
          </Box>
        )}
      </Stack>
    </Box>
  );
}
