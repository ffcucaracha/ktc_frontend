import { Box, Chip, Paper, Stack, Typography } from "@mui/material";

import type { OperatorError, SimulationTimelineEvent } from "../../entities/training/api/types";
import {
  buildResultTimelineItems,
  formatDurationMs,
  type ResultTimelineItem,
} from "../../entities/training/lib/result";

interface TrainingTimelineProps {
  timeline: SimulationTimelineEvent[];
  errors: OperatorError[];
}

function chipLabel(item: ResultTimelineItem): string {
  if (item.kind === "risk") return item.predictionTriggered ? "AI предупредил" : "ML риск";
  if (item.kind === "error") return "Ошибка";
  if (item.kind === "action") return "Действие";
  if (item.kind === "alarm") return "Сигнал";
  if (item.kind === "state") return "Snapshot";
  return "Сессия";
}

function chipColor(item: ResultTimelineItem): "default" | "error" | "warning" | "info" | "success" {
  if (item.kind === "error") return "error";
  if (item.kind === "risk") {
    if (item.predictionTriggered) return (item.risk ?? 0) >= 0.7 ? "error" : "warning";
    return "info";
  }
  if (item.kind === "alarm") return "warning";
  if (item.kind === "action") return "info";
  if (item.kind === "session") return "success";
  return "default";
}

export function TrainingTimeline({ timeline, errors }: TrainingTimelineProps): JSX.Element {
  const items = buildResultTimelineItems(timeline, errors);

  if (items.length === 0) {
    return (
      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2 }}>
        <Typography color="text.secondary">Ключевые события для этой сессии не найдены.</Typography>
      </Paper>
    );
  }

  return (
    <Stack spacing={1.25}>
      {items.map((item) => (
        <Paper
          key={item.id}
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: item.kind === "error" ? "error.light" : item.predictionTriggered ? "warning.light" : "divider",
            p: 1.5,
          }}
        >
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
            <Box sx={{ minWidth: 90 }}>
              <Typography variant="caption" color="text.secondary">
                {item.simulationTimeMs === null ? "время —" : `t = ${formatDurationMs(item.simulationTimeMs)}`}
              </Typography>
            </Box>
            <Chip size="small" label={chipLabel(item)} color={chipColor(item)} sx={{ alignSelf: "flex-start" }} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle2">{item.title}</Typography>
              <Typography variant="body2" color="text.secondary">
                {item.detail}
              </Typography>
            </Box>
          </Stack>
        </Paper>
      ))}
    </Stack>
  );
}
