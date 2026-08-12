import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  getSimulationState,
  sendSimulationCommand,
} from "../../../entities/simulation/api/simulationApi";
import type { Alarm, SimulationEvent, SimulationState } from "../../../entities/simulation/api/types";
import {
  parseSimulationEvent,
  parseSimulationState,
  parseAlarm,
  readStringData,
} from "../../../entities/simulation/lib/validation";
import { simulationSessionsQueryKey } from "../../../entities/simulation/model/queries";
import { ApiClientError } from "../../../shared/api/client";
import { getAccessToken } from "../../../shared/auth/authStore";
import { createUuidV4 } from "../../../shared/lib/uuid";

type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected";
type CommandStatus = "pending" | "accepted" | "rejected" | "failed";
export type PumpId = "steam_supply_pump" | "steam_exhaust_pump";
export type PumpAction = "start" | "stop";

export interface CommandLogItem {
  commandId: string;
  equipmentId: PumpId;
  action: PumpAction;
  status: CommandStatus;
  message: string;
}

interface RuntimeState {
  state: SimulationState | null;
  connectionStatus: ConnectionStatus;
  commands: CommandLogItem[];
  errors: string[];
}

interface RuntimeActions {
  sendPumpCommand: (equipmentId: PumpId, action: PumpAction) => Promise<void>;
  isCommandPending: (equipmentId: PumpId, action: PumpAction) => boolean;
}

const reconnectDelays = [500, 1_000, 2_000, 4_000, 8_000];

function wsBaseUrl(): string {
  return import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000/ws/v1";
}

function commandMessage(equipmentId: PumpId, action: PumpAction): string {
  const pump = equipmentId === "steam_supply_pump" ? "Насос подачи" : "Насос откачки";
  return `${pump}: ${action === "start" ? "запуск" : "останов"}`;
}

function normalizeError(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.code === "SIMULATION_TIMEOUT") {
      return "Команда не выполнена: сервис моделирования не ответил.";
    }
    return error.message;
  }
  return "Команда не выполнена.";
}

export function useBoilerRuntime(sessionId: string, initialState: SimulationState | null): RuntimeState & RuntimeActions {
  const queryClient = useQueryClient();
  const [state, setState] = useState<SimulationState | null>(initialState);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const [commands, setCommands] = useState<CommandLogItem[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const manuallyClosedRef = useRef(false);
  const stateRef = useRef<SimulationState | null>(initialState);
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

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

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
  }, [applyState, queryClient, sessionId]);

  const addError = useCallback((message: string): void => {
    setErrors((current) => [message, ...current].slice(0, 5));
  }, []);

  const updateCommand = useCallback((commandId: string, status: CommandStatus, message?: string): void => {
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
  }, []);

  const applyAlarm = useCallback((alarm: Alarm, active: boolean): void => {
    setState((current) => {
      if (current === null) {
        return current;
      }
      const remaining = current.alarms.filter((item) => item.code !== alarm.code);
      return {
        ...current,
        alarms: active ? [...remaining, { ...alarm, active: true }] : remaining,
      };
    });
  }, []);

  const handleEvent = useCallback(
    (event: SimulationEvent): void => {
      if (event.type === "state.snapshot" || event.type === "state.patch") {
        const nextState = parseSimulationState(event.data);
        if (nextState !== null) {
          applyState(nextState);
        }
        return;
      }
      if (event.type === "command.accepted") {
        const commandId = readStringData(event.data, "command_id");
        if (commandId !== null) {
          updateCommand(commandId, "pending", "Команда принята, ждём состояние");
        }
        return;
      }
      if (event.type === "command.rejected") {
        const commandId = readStringData(event.data, "command_id");
        const message = readStringData(event.data, "message") ?? "Команда отклонена";
        if (commandId !== null) {
          updateCommand(commandId, "rejected", message);
        }
        addError(message);
        return;
      }
      if (event.type === "alarm.raised" || event.type === "alarm.cleared") {
        const parsedAlarm = parseAlarm(event.data);
        if (parsedAlarm !== null) {
          applyAlarm(parsedAlarm, event.type === "alarm.raised");
        }
        return;
      }
      if (event.type === "integration.error") {
        addError(readStringData(event.data, "message") ?? "Ошибка сервиса моделирования");
      }
    },
    [addError, applyAlarm, applyState, updateCommand],
  );

  useEffect(() => {
    manuallyClosedRef.current = false;

    const connect = (): void => {
      const token = getAccessToken();
      if (token === null) {
        setConnectionStatus("disconnected");
        return;
      }
      setConnectionStatus(reconnectAttemptRef.current === 0 ? "connecting" : "reconnecting");
      const socket = new WebSocket(
        `${wsBaseUrl()}/simulation-sessions/${sessionId}?access_token=${encodeURIComponent(token)}`,
      );
      socketRef.current = socket;

      socket.onopen = () => {
        reconnectAttemptRef.current = 0;
        setConnectionStatus("connected");
      };
      socket.onmessage = (messageEvent: MessageEvent<string>) => {
        let payload: unknown;
        try {
          payload = JSON.parse(messageEvent.data);
        } catch {
          addError("Получено некорректное событие WebSocket");
          return;
        }
        const event = parseSimulationEvent(payload);
        if (event === null) {
          addError("Получено неизвестное событие WebSocket");
          return;
        }
        handleEvent(event);
      };
      socket.onclose = () => {
        if (manuallyClosedRef.current) {
          setConnectionStatus("disconnected");
          return;
        }
        const delay = reconnectDelays[Math.min(reconnectAttemptRef.current, reconnectDelays.length - 1)];
        reconnectAttemptRef.current += 1;
        setConnectionStatus("reconnecting");
        reconnectTimerRef.current = window.setTimeout(() => {
          void refreshSnapshot().catch(() => {
            addError("Не удалось обновить snapshot после reconnect");
          });
          connect();
        }, delay);
      };
      socket.onerror = () => {
        socket.close();
      };
    };

    connect();

    return () => {
      manuallyClosedRef.current = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      socketRef.current?.close();
    };
  }, [addError, handleEvent, refreshSnapshot, sessionId]);

  const sendPumpCommand = useCallback(
    async (equipmentId: PumpId, action: PumpAction): Promise<void> => {
      const pendingKey = `${equipmentId}:${action}`;
      if (pendingKeysRef.current.has(pendingKey)) {
        return;
      }
      pendingKeysRef.current.add(pendingKey);
      const commandId = createUuidV4();
      const item: CommandLogItem = {
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
        }
        if (response.status === "failed") {
          updateCommand(commandId, "failed", response.external_error_message ?? "Команда не выполнена");
          addError(response.external_error_message ?? "Команда не выполнена");
        }
      } catch (error) {
        const message = normalizeError(error);
        updateCommand(commandId, "failed", message);
        addError(message);
      }
    },
    [addError, sessionId, state?.revision, updateCommand],
  );

  const isCommandPending = useCallback(
    (equipmentId: PumpId, action: PumpAction): boolean =>
      commands.some((command) => command.equipmentId === equipmentId && command.action === action && command.status === "pending"),
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
