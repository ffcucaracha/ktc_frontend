import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Chip,
  LinearProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

import { createTrainingEventSocket } from "../../entities/training/api/trainingApi";
import type { RiskPrediction, TrainingRealtimeEvent } from "../../entities/training/api/types";
import {
  buildCoachMessage,
  formatRiskPercent,
  isMockRiskModel,
  isRiskModelUnavailable,
} from "../../entities/training/lib/format";

type SocketStatus = "connecting" | "connected" | "unavailable";

interface AiCoachPanelProps {
  sessionId: string;
}

function parseRiskPrediction(event: MessageEvent<string>): RiskPrediction | null {
  try {
    const payload = JSON.parse(event.data) as TrainingRealtimeEvent;
    if (payload.type !== "ai.risk.updated") {
      return null;
    }
    const data = payload.data;
    if (
      typeof data.risk !== "number" ||
      typeof data.horizon_seconds !== "number" ||
      typeof data.model_version !== "string"
    ) {
      return null;
    }
    return {
      risk: data.risk,
      predicted_error_code:
        typeof data.predicted_error_code === "string" ? data.predicted_error_code : null,
      horizon_seconds: data.horizon_seconds,
      model_version: data.model_version,
      features: Array.isArray(data.features)
        ? data.features.filter(
            (item): item is { name: string; importance: number } =>
              typeof item === "object" &&
              item !== null &&
              "name" in item &&
              typeof item.name === "string" &&
              "importance" in item &&
              typeof item.importance === "number",
          )
        : [],
    };
  } catch {
    return null;
  }
}

export function AiCoachPanel({ sessionId }: AiCoachPanelProps): JSX.Element {
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("connecting");
  const [prediction, setPrediction] = useState<RiskPrediction | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;

    const connect = (): void => {
      if (disposed) {
        return;
      }
      setSocketStatus("connecting");
      try {
        socket = createTrainingEventSocket(sessionId);
      } catch {
        setSocketStatus("unavailable");
        return;
      }

      socket.onopen = () => {
        if (!disposed) {
          setSocketStatus("connected");
        }
      };
      socket.onmessage = (event: MessageEvent<string>) => {
        const nextPrediction = parseRiskPrediction(event);
        if (nextPrediction !== null && !disposed) {
          setPrediction(nextPrediction);
          setUpdatedAt(new Date());
        }
      };
      socket.onerror = () => {
        if (!disposed) {
          setSocketStatus("unavailable");
        }
      };
      socket.onclose = () => {
        if (disposed) {
          return;
        }
        setSocketStatus("unavailable");
        reconnectTimerRef.current = window.setTimeout(connect, 2_500);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      socket?.close();
    };
  }, [sessionId]);

  const message = useMemo(
    () => (prediction === null ? null : buildCoachMessage(prediction, updatedAt ?? new Date())),
    [prediction, updatedAt],
  );
  const modelUnavailable = prediction !== null && isRiskModelUnavailable(prediction.model_version);
  const mockModel = prediction !== null && isMockRiskModel(prediction.model_version);

  return (
    <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2, minWidth: 0 }}>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
          <Box>
            <Typography variant="overline" color="text.secondary">
              Интеллектуальная поддержка
            </Typography>
            <Typography variant="h6">AI-инструктор</Typography>
          </Box>
          <Chip
            size="small"
            label={
              socketStatus === "connected"
                ? "подключён"
                : socketStatus === "connecting"
                  ? "подключение"
                  : "недоступен"
            }
            color={socketStatus === "connected" ? "success" : "default"}
          />
        </Stack>

        {socketStatus === "unavailable" && prediction === null ? (
          <Alert severity="warning">
            AI временно недоступен. Управление установкой продолжает работать независимо от него.
          </Alert>
        ) : null}

        {modelUnavailable ? (
          <Alert severity="warning">
            ML-модель риска ещё не загружена. Тренажёр продолжает работать без прогноза.
          </Alert>
        ) : null}

        {mockModel ? (
          <Alert severity="info">
            Используется контрактная AI-заглушка. Для реального прогноза включите HTTP gateway и обученную модель.
          </Alert>
        ) : null}

        {message === null ? (
          <Typography color="text.secondary" variant="body2">
            Ожидаем первый прогноз по текущей телеметрии.
          </Typography>
        ) : (
          <Stack spacing={1.5}>
            <Box>
              <Stack direction="row" justifyContent="space-between" spacing={1}>
                <Typography fontWeight={600}>{message.title}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {formatRiskPercent(message.risk)}
                </Typography>
              </Stack>
              <LinearProgress
                variant="determinate"
                value={Math.max(0, Math.min(100, message.risk * 100))}
                color={message.risk >= 0.7 ? "error" : message.risk >= 0.5 ? "warning" : "success"}
                sx={{ mt: 1, height: 8, borderRadius: 999 }}
              />
            </Box>

            {message.predictedErrorCode !== null ? (
              <Chip
                size="small"
                color="warning"
                label={`Прогноз: ${message.predictedErrorCode}`}
                sx={{ alignSelf: "flex-start" }}
              />
            ) : null}

            <Box>
              <Typography variant="caption" color="text.secondary">
                Причина
              </Typography>
              <Typography variant="body2">{message.reason}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Рекомендация
              </Typography>
              <Typography variant="body2">{message.recommendation}</Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              Обновлено {message.updatedAt.toLocaleTimeString("ru-RU")} · горизонт {prediction?.horizon_seconds ?? 10} с
            </Typography>
          </Stack>
        )}
      </Stack>
    </Paper>
  );
}
