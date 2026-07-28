import { Box, Button, Typography } from "@mui/material";

import type { SimulationState } from "../../entities/simulation/api/types";
import type { PumpAction, PumpId } from "./model/useBoilerRuntime";

interface BoilerSchemeProps {
  state: SimulationState | null;
  onCommand: (equipmentId: PumpId, action: PumpAction) => void;
  isCommandPending: (equipmentId: PumpId, action: PumpAction) => boolean;
}

function pumpColor(status: string | undefined): string {
  if (status === "running") {
    return "#2e7d32";
  }
  if (status === "fault" || status === "unavailable") {
    return "#c62828";
  }
  return "#607d8b";
}

interface PumpControlsProps {
  equipmentId: PumpId;
  actionLabel: string;
  stopLabel: string;
  status: string | undefined;
  left: string;
  top: string;
  onCommand: (equipmentId: PumpId, action: PumpAction) => void;
  isCommandPending: (equipmentId: PumpId, action: PumpAction) => boolean;
}

function PumpControls({
  equipmentId,
  actionLabel,
  stopLabel,
  status,
  left,
  top,
  onCommand,
  isCommandPending,
}: PumpControlsProps): JSX.Element {
  const action: PumpAction = status === "running" ? "stop" : "start";
  const label = action === "stop" ? "Stop" : "Start";
  const ariaLabel = action === "stop" ? stopLabel : actionLabel;

  return (
    <Button
      variant="contained"
      aria-label={ariaLabel}
      onClick={() => onCommand(equipmentId, action)}
      disabled={isCommandPending(equipmentId, action) || status === undefined}
      sx={{
        bgcolor: action === "stop" ? "error.main" : "success.dark",
        border: "5px solid",
        borderColor: "background.paper",
        borderRadius: "50%",
        boxShadow: 3,
        color: "common.white",
        fontSize: { xs: 11, sm: 12 },
        fontWeight: 700,
        height: { xs: 62, sm: 72 },
        left,
        minWidth: 0,
        p: 0,
        position: "absolute",
        top,
        transform: "translate(-50%, -50%)",
        width: { xs: 62, sm: 72 },
        "&:hover": {
          bgcolor: action === "stop" ? "error.dark" : "success.main",
        },
      }}
    >
      {label}
    </Button>
  );
}

export function BoilerScheme({
  state,
  onCommand,
  isCommandPending,
}: BoilerSchemeProps): JSX.Element {
  const supplyStatus = state?.equipment.steam_supply_pump?.status;
  const exhaustStatus = state?.equipment.steam_exhaust_pump?.status;
  const temperature = state?.boiler.temperature_c;
  const pressure = state?.boiler.pressure_bar;

  return (
    <Box>
      <Box sx={{ position: "relative" }}>
        <svg
          role="img"
          aria-labelledby="boiler-title boiler-desc"
          viewBox="0 0 760 360"
          width="100%"
          style={{ maxHeight: 420 }}
        >
          <title id="boiler-title">Мнемосхема котла с двумя насосами</title>
          <desc id="boiler-desc">
            Котёл, насос подачи пара, насос откачки пара, линии потока, температура и давление.
          </desc>
          <rect x="0" y="0" width="760" height="360" rx="8" fill="#f8faf9" />
          <line x1="165" y1="180" x2="285" y2="180" stroke="#607d8b" strokeWidth="16" />
          <line x1="475" y1="180" x2="595" y2="180" stroke="#607d8b" strokeWidth="16" />
          <path d="M 285 180 C 310 100, 450 100, 475 180" fill="none" stroke="#90a4ae" strokeWidth="10" />
          <path d="M 285 180 C 310 260, 450 260, 475 180" fill="none" stroke="#90a4ae" strokeWidth="10" />

          <g aria-label={`Насос подачи пара: ${supplyStatus ?? "нет данных"}`}>
            <circle cx="125" cy="180" r="42" fill={pumpColor(supplyStatus)} />
            <circle cx="125" cy="180" r="24" fill="#ffffff" opacity="0.86" />
            <text x="125" y="245" textAnchor="middle" fontSize="18" fill="#263238">
              steam_supply_pump
            </text>
            <text x="125" y="274" textAnchor="middle" fontSize="16" fill="#455a64">
              {supplyStatus ?? "unknown"}
            </text>
          </g>

          <g aria-label="Котёл">
            <rect x="300" y="85" width="160" height="190" rx="78" fill="#cfd8dc" stroke="#455a64" strokeWidth="4" />
            <rect x="330" y="125" width="100" height="110" rx="42" fill="#eceff1" />
            <text x="380" y="168" textAnchor="middle" fontSize="22" fill="#263238">
              Котёл
            </text>
            <text x="380" y="202" textAnchor="middle" fontSize="18" fill="#455a64">
              {temperature === undefined ? "T: --" : `T: ${temperature.toFixed(1)} C`}
            </text>
            <text x="380" y="230" textAnchor="middle" fontSize="18" fill="#455a64">
              {pressure === undefined ? "P: --" : `P: ${pressure.toFixed(1)} bar`}
            </text>
          </g>

          <g aria-label={`Насос откачки пара: ${exhaustStatus ?? "нет данных"}`}>
            <circle cx="635" cy="180" r="42" fill={pumpColor(exhaustStatus)} />
            <circle cx="635" cy="180" r="24" fill="#ffffff" opacity="0.86" />
            <text x="635" y="245" textAnchor="middle" fontSize="18" fill="#263238">
              steam_exhaust_pump
            </text>
            <text x="635" y="274" textAnchor="middle" fontSize="16" fill="#455a64">
              {exhaustStatus ?? "unknown"}
            </text>
          </g>
        </svg>
        <PumpControls
          equipmentId="steam_supply_pump"
          actionLabel="Запустить steam_supply_pump"
          stopLabel="Остановить steam_supply_pump"
          status={supplyStatus}
          left="16.5%"
          top="50%"
          onCommand={onCommand}
          isCommandPending={isCommandPending}
        />
        <PumpControls
          equipmentId="steam_exhaust_pump"
          actionLabel="Запустить steam_exhaust_pump"
          stopLabel="Остановить steam_exhaust_pump"
          status={exhaustStatus}
          left="83.5%"
          top="50%"
          onCommand={onCommand}
          isCommandPending={isCommandPending}
        />
      </Box>
      <Typography color="text.secondary" variant="body2">
        Значения отображаются только из авторитетного состояния backend.
      </Typography>
    </Box>
  );
}
