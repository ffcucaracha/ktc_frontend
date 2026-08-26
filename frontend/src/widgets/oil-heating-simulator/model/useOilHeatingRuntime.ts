import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  getSimulationState,
  sendSimulationCommand,
} from "../../../entities/simulation/api/simulationApi";
import type { SimulationState } from "../../../entities/simulation/api/types";
import { simulationSessionsQueryKey } from "../../../entities/simulation/model/queries";
import { ApiClientError } from "../../../shared/api/client";
import { createUuidV4 } from "../../../shared/lib/uuid";

type ConnectionStatus = "connected" | "disconnected";
type CommandStatus = "pending" | "accepted" | "rejected" | "failed";
export type OilPumpId = "H1A" | "H1B" | "H1C";
export type OilValveId = "KR1" | "KR2" | "KR3" | "KR4" | "KR5" | "KR6";
export type OilRegulatorId = "FRC404" | "FRC405" | "FRC406";
export type OilDosingId = "ND1";
export type ElouRegulatorId = "FRC407" | "FRC408";
export type ElouPumpId = "ND2" | "H3";
export type ElouValveId = "KR7" | "KR8";
export type ElouEquipmentId = ElouRegulatorId | ElouPumpId | ElouValveId | "E1";
export type OilEquipmentId =
  | OilPumpId
  | OilRegulatorId
  | OilValveId
  | OilDosingId
  | ElouEquipmentId
  | "plant";
export type OilPumpAction = "start" | "stop";
export type OilValveAction = "open" | "close";
export type OilRegulatorAction = "set";
export type OilDosingAction = "start" | "stop" | "set";
export type OilPlantAction = "reset";
export type ElouVoltageAction = "apply_voltage";
export type OilCommandAction =
  | OilPumpAction
  | OilValveAction
  | OilRegulatorAction
  | OilDosingAction
  | OilPlantAction
  | ElouVoltageAction;

export interface OilCommandLogItem {
  commandId: string;
  equipmentId: OilEquipmentId;
  action: OilCommandAction;
  status: CommandStatus;
  message: string;
}

interface RuntimeState {
  state: SimulationState | null;
  connectionStatus: ConnectionStatus;
  commands: OilCommandLogItem[];
  errors: string[];
}

interface RuntimeActions {
  sendPumpCommand: (equipmentId: OilPumpId, action: OilPumpAction) => Promise<void>;
  sendValveCommand: (equipmentId: OilValveId, action: OilValveAction) => Promise<void>;
  sendRegulatorCommand: (equipmentId: OilRegulatorId, value: number) => Promise<void>;
  sendDosingCommand: (action: OilDosingAction, value?: number) => Promise<void>;
  sendElouPumpCommand: (equipmentId: ElouPumpId, action: OilPumpAction) => Promise<void>;
  sendElouValveCommand: (equipmentId: ElouValveId, action: OilValveAction) => Promise<void>;
  sendElouRegulatorCommand: (equipmentId: ElouRegulatorId, value: number) => Promise<void>;
  sendElouDosingCommand: (action: OilDosingAction, value?: number) => Promise<void>;
  sendElouVoltageCommand: () => Promise<void>;
  sendResetCommand: () => Promise<void>;
  isCommandPending: (equipmentId: OilPumpId, action: OilPumpAction) => boolean;
  isValveCommandPending: (equipmentId: OilValveId, action: OilValveAction) => boolean;
  isRegulatorCommandPending: (equipmentId: OilRegulatorId) => boolean;
  isDosingCommandPending: (action: OilDosingAction) => boolean;
  isElouPumpCommandPending: (equipmentId: ElouPumpId, action: OilPumpAction) => boolean;
  isElouValveCommandPending: (equipmentId: ElouValveId, action: OilValveAction) => boolean;
  isElouRegulatorCommandPending: (equipmentId: ElouRegulatorId) => boolean;
  isElouDosingCommandPending: (action: OilDosingAction) => boolean;
  isElouVoltageCommandPending: () => boolean;
  isResetCommandPending: () => boolean;
}

const pollingIntervalMs = 2_000;

function commandMessage(equipmentId: OilPumpId, action: OilPumpAction): string {
  return `Насос ${equipmentId}: ${action === "start" ? "пуск" : "останов"}`;
}

function valveCommandMessage(equipmentId: OilValveId, action: OilValveAction): string {
  return `Кран ${equipmentId}: ${action === "open" ? "открыть" : "закрыть"}`;
}

function regulatorCommandMessage(equipmentId: OilRegulatorId, value: number): string {
  return `Регулятор ${equipmentId}: ${value}%`;
}

function dosingCommandMessage(action: OilDosingAction, value?: number): string {
  if (action === "set") {
    return `Дозатор ND1: ${value ?? 0} г/т`;
  }
  return `Дозатор ND1: ${action === "start" ? "пуск" : "останов"}`;
}

function elouRegulatorCommandMessage(equipmentId: ElouRegulatorId, value: number): string {
  return `ЭЛОУ ${equipmentId}: ${value}%`;
}

function elouPumpCommandMessage(equipmentId: ElouPumpId, action: OilPumpAction): string {
  return `ЭЛОУ ${equipmentId}: ${action === "start" ? "пуск" : "останов"}`;
}

function elouValveCommandMessage(equipmentId: ElouValveId, action: OilValveAction): string {
  return `ЭЛОУ ${equipmentId}: ${action === "open" ? "открыть" : "закрыть"}`;
}

function elouDosingCommandMessage(action: OilDosingAction, value?: number): string {
  if (action === "set") {
    return `ЭЛОУ ND2: ${value ?? 0} г/т`;
  }
  return `ЭЛОУ ND2: ${action === "start" ? "пуск" : "останов"}`;
}

function normalizeError(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.code === "SIMULATION_TIMEOUT") {
      return "Команда не выполнена: ktc_backend не ответил.";
    }
    return error.message;
  }
  return "Команда не выполнена.";
}

export function useOilHeatingRuntime(
  sessionId: string,
  initialState: SimulationState | null,
  enabled = true,
): RuntimeState & RuntimeActions {
  const queryClient = useQueryClient();
  const [state, setState] = useState<SimulationState | null>(initialState);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connected");
  const [commands, setCommands] = useState<OilCommandLogItem[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const pendingKeysRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (initialState !== null) {
      setState((current) => {
        if (current !== null && initialState.revision < current.revision) {
          return current;
        }
        return initialState;
      });
    }
  }, [initialState]);

  const applyState = useCallback((nextState: SimulationState): void => {
    setState((current) => {
      if (current !== null && nextState.revision < current.revision) {
        return current;
      }
      setCommands((currentCommands) =>
        currentCommands.map((command) =>
          command.status === "pending" ? { ...command, status: "accepted" } : command,
        ),
      );
      pendingKeysRef.current.clear();
      return nextState;
    });
  }, []);

  const refreshSnapshot = useCallback(async (): Promise<void> => {
    const snapshot = await getSimulationState(sessionId);
    applyState(snapshot);
    queryClient.setQueryData([...simulationSessionsQueryKey, sessionId, "state"], snapshot);
    setConnectionStatus("connected");
  }, [applyState, queryClient, sessionId]);

  const addError = useCallback((message: string): void => {
    setErrors((current) => [message, ...current].slice(0, 5));
  }, []);

  const updateCommand = useCallback(
    (commandId: string, status: CommandStatus, message?: string): void => {
      setCommands((current) =>
        current.map((command) => {
          if (command.commandId !== commandId) {
            return command;
          }
          if (status === "rejected" || status === "failed") {
            pendingKeysRef.current.delete(`${command.equipmentId}:${command.action}`);
          }
          return { ...command, status, message: message ?? command.message };
        }),
      );
    },
    [],
  );

  const sendCommand = useCallback(
    async (
      equipmentId: OilEquipmentId,
      action: OilCommandAction,
      payload: Record<string, unknown>,
      message: string,
      pendingActionKey = action,
    ): Promise<void> => {
      if (!enabled) {
        return;
      }
      const pendingKey = `${equipmentId}:${pendingActionKey}`;
      if (pendingKeysRef.current.has(pendingKey)) {
        return;
      }
      pendingKeysRef.current.add(pendingKey);
      const commandId = createUuidV4();
      const item: OilCommandLogItem = {
        commandId,
        equipmentId,
        action,
        status: "pending",
        message,
      };
      setCommands((current) => [item, ...current].slice(0, 20));
      try {
        const response = await sendSimulationCommand(sessionId, {
          command_id: commandId,
          equipment_id: equipmentId,
          action,
          payload,
          expected_revision: state?.revision,
        });
        if (response.status === "rejected") {
          updateCommand(commandId, "rejected", response.external_error_message ?? "Команда отклонена");
          addError(response.external_error_message ?? "Команда отклонена");
          return;
        }
        if (response.status === "failed") {
          updateCommand(commandId, "failed", response.external_error_message ?? "Команда не выполнена");
          addError(response.external_error_message ?? "Команда не выполнена");
          return;
        }
        await refreshSnapshot();
      } catch (error) {
        const errorMessage = normalizeError(error);
        updateCommand(commandId, "failed", errorMessage);
        addError(errorMessage);
      }
    },
    [addError, enabled, refreshSnapshot, sessionId, state?.revision, updateCommand],
  );

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let ignore = false;
    const refresh = (): void => {
      void refreshSnapshot().catch(() => {
        if (!ignore) {
          setConnectionStatus("disconnected");
        }
      });
    };

    refresh();
    const intervalId = window.setInterval(refresh, pollingIntervalMs);
    return () => {
      ignore = true;
      window.clearInterval(intervalId);
    };
  }, [enabled, refreshSnapshot]);

  const sendPumpCommand = useCallback(
    async (equipmentId: OilPumpId, action: OilPumpAction): Promise<void> => {
      await sendCommand(equipmentId, action, {}, commandMessage(equipmentId, action));
    },
    [sendCommand],
  );

  const sendValveCommand = useCallback(
    async (equipmentId: OilValveId, action: OilValveAction): Promise<void> => {
      await sendCommand(equipmentId, action, {}, valveCommandMessage(equipmentId, action));
    },
    [sendCommand],
  );

  const sendRegulatorCommand = useCallback(
    async (equipmentId: OilRegulatorId, value: number): Promise<void> => {
      const normalizedValue = Math.round(value);
      await sendCommand(
        equipmentId,
        "set",
        { value: normalizedValue },
        regulatorCommandMessage(equipmentId, normalizedValue),
        "set",
      );
    },
    [sendCommand],
  );

  const sendDosingCommand = useCallback(
    async (action: OilDosingAction, value?: number): Promise<void> => {
      const payload = action === "set" ? { value: Math.round(value ?? 0) } : {};
      await sendCommand("ND1", action, payload, dosingCommandMessage(action, value), action);
    },
    [sendCommand],
  );

  const sendElouPumpCommand = useCallback(
    async (equipmentId: ElouPumpId, action: OilPumpAction): Promise<void> => {
      await sendCommand(equipmentId, action, {}, elouPumpCommandMessage(equipmentId, action));
    },
    [sendCommand],
  );

  const sendElouValveCommand = useCallback(
    async (equipmentId: ElouValveId, action: OilValveAction): Promise<void> => {
      await sendCommand(equipmentId, action, {}, elouValveCommandMessage(equipmentId, action));
    },
    [sendCommand],
  );

  const sendElouRegulatorCommand = useCallback(
    async (equipmentId: ElouRegulatorId, value: number): Promise<void> => {
      const normalizedValue = Math.round(value);
      await sendCommand(
        equipmentId,
        "set",
        { value: normalizedValue },
        elouRegulatorCommandMessage(equipmentId, normalizedValue),
        "set",
      );
    },
    [sendCommand],
  );

  const sendElouDosingCommand = useCallback(
    async (action: OilDosingAction, value?: number): Promise<void> => {
      const payload = action === "set" ? { value: Math.round(value ?? 0) } : {};
      await sendCommand("ND2", action, payload, elouDosingCommandMessage(action, value), action);
    },
    [sendCommand],
  );

  const sendElouVoltageCommand = useCallback(async (): Promise<void> => {
    await sendCommand("E1", "apply_voltage", {}, "ЭЛОУ E1: подать напряжение");
  }, [sendCommand]);

  const sendResetCommand = useCallback(async (): Promise<void> => {
    await sendCommand("plant", "reset", {}, "Сброс процесса", "reset");
  }, [sendCommand]);

  const isPending = useCallback(
    (equipmentId: OilEquipmentId, action: OilCommandAction): boolean =>
      commands.some(
        (command) =>
          command.equipmentId === equipmentId &&
          command.action === action &&
          command.status === "pending",
      ),
    [commands],
  );

  const isCommandPending = useCallback(
    (equipmentId: OilPumpId, action: OilPumpAction): boolean =>
      isPending(equipmentId, action),
    [isPending],
  );

  const isValveCommandPending = useCallback(
    (equipmentId: OilValveId, action: OilValveAction): boolean =>
      isPending(equipmentId, action),
    [isPending],
  );

  const isRegulatorCommandPending = useCallback(
    (equipmentId: OilRegulatorId): boolean =>
      isPending(equipmentId, "set"),
    [isPending],
  );

  const isDosingCommandPending = useCallback(
    (action: OilDosingAction): boolean => isPending("ND1", action),
    [isPending],
  );

  const isElouPumpCommandPending = useCallback(
    (equipmentId: ElouPumpId, action: OilPumpAction): boolean =>
      isPending(equipmentId, action),
    [isPending],
  );

  const isElouValveCommandPending = useCallback(
    (equipmentId: ElouValveId, action: OilValveAction): boolean =>
      isPending(equipmentId, action),
    [isPending],
  );

  const isElouRegulatorCommandPending = useCallback(
    (equipmentId: ElouRegulatorId): boolean => isPending(equipmentId, "set"),
    [isPending],
  );

  const isElouDosingCommandPending = useCallback(
    (action: OilDosingAction): boolean => isPending("ND2", action),
    [isPending],
  );

  const isElouVoltageCommandPending = useCallback(
    (): boolean => isPending("E1", "apply_voltage"),
    [isPending],
  );

  const isResetCommandPending = useCallback(
    (): boolean => isPending("plant", "reset"),
    [isPending],
  );

  return useMemo(
    () => ({
      state,
      connectionStatus,
      commands,
      errors,
      sendPumpCommand,
      sendValveCommand,
      sendRegulatorCommand,
      sendDosingCommand,
      sendElouPumpCommand,
      sendElouValveCommand,
      sendElouRegulatorCommand,
      sendElouDosingCommand,
      sendElouVoltageCommand,
      sendResetCommand,
      isCommandPending,
      isValveCommandPending,
      isRegulatorCommandPending,
      isDosingCommandPending,
      isElouPumpCommandPending,
      isElouValveCommandPending,
      isElouRegulatorCommandPending,
      isElouDosingCommandPending,
      isElouVoltageCommandPending,
      isResetCommandPending,
    }),
    [
      commands,
      connectionStatus,
      errors,
      isCommandPending,
      isValveCommandPending,
      isRegulatorCommandPending,
      isDosingCommandPending,
      isElouPumpCommandPending,
      isElouValveCommandPending,
      isElouRegulatorCommandPending,
      isElouDosingCommandPending,
      isElouVoltageCommandPending,
      isResetCommandPending,
      sendDosingCommand,
      sendElouPumpCommand,
      sendElouValveCommand,
      sendElouRegulatorCommand,
      sendElouDosingCommand,
      sendElouVoltageCommand,
      sendPumpCommand,
      sendValveCommand,
      sendRegulatorCommand,
      sendResetCommand,
      state,
    ],
  );
}
