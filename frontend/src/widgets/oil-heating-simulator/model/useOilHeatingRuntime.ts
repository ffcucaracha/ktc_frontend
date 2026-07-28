import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  getSimulationState,
  sendSimulationCommand,
} from "../../../entities/simulation/api/simulationApi";
import type { SimulationState } from "../../../entities/simulation/api/types";
import { simulationSessionsQueryKey } from "../../../entities/simulation/model/queries";
import { ApiClientError } from "../../../shared/api/client";

type ConnectionStatus = "connected" | "disconnected";
type CommandStatus = "pending" | "accepted" | "rejected" | "failed";
export type OilPumpId = "H1A" | "H1B" | "H1V";
export type OilPumpAction = "start" | "stop";

export interface OilCommandLogItem {
  commandId: string;
  equipmentId: OilPumpId;
  action: OilPumpAction;
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
  isCommandPending: (equipmentId: OilPumpId, action: OilPumpAction) => boolean;
}

const pollingIntervalMs = 2_000;

function commandMessage(equipmentId: OilPumpId, action: OilPumpAction): string {
  return `Насос ${equipmentId}: ${action === "start" ? "пуск" : "останов"}`;
}

function createCommandId(): string {
  if (globalThis.crypto?.randomUUID !== undefined) {
    return globalThis.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
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

  useEffect(() => {
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
  }, [refreshSnapshot]);

  const sendPumpCommand = useCallback(
    async (equipmentId: OilPumpId, action: OilPumpAction): Promise<void> => {
      const pendingKey = `${equipmentId}:${action}`;
      if (pendingKeysRef.current.has(pendingKey)) {
        return;
      }
      pendingKeysRef.current.add(pendingKey);
      const commandId = createCommandId();
      const item: OilCommandLogItem = {
        commandId,
        equipmentId,
        action,
        status: "pending",
        message: commandMessage(equipmentId, action),
      };
      setCommands((current) => [item, ...current].slice(0, 20));
      try {
        const response = await sendSimulationCommand(sessionId, {
          command_id: commandId,
          equipment_id: equipmentId,
          action,
          payload: {},
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
        const message = normalizeError(error);
        updateCommand(commandId, "failed", message);
        addError(message);
      }
    },
    [addError, refreshSnapshot, sessionId, state?.revision, updateCommand],
  );

  const isCommandPending = useCallback(
    (equipmentId: OilPumpId, action: OilPumpAction): boolean =>
      commands.some(
        (command) =>
          command.equipmentId === equipmentId &&
          command.action === action &&
          command.status === "pending",
      ),
    [commands],
  );

  return useMemo(
    () => ({
      state,
      connectionStatus,
      commands,
      errors,
      sendPumpCommand,
      isCommandPending,
    }),
    [commands, connectionStatus, errors, isCommandPending, sendPumpCommand, state],
  );
}
