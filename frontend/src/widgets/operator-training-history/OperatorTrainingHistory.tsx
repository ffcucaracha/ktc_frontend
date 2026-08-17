import {
  Box,
  Card,
  CardContent,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

import type { TrainingResult } from "../../entities/training/api/types";
import {
  aggregateOperatorTrainingStats,
  formatReactionTime,
  formatScore,
} from "../../entities/training/lib/admin";

interface OperatorTrainingHistoryProps {
  results: TrainingResult[];
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("ru-RU");
}

export function OperatorTrainingHistory({ results }: OperatorTrainingHistoryProps): JSX.Element {
  const stats = aggregateOperatorTrainingStats(results);
  const recent = results.slice(0, 5);

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        {[
          ["Тренировок", String(stats.sessions)],
          ["Средний балл", formatScore(stats.averageScore)],
          ["Среднее время реакции", formatReactionTime(stats.averageReactionTimeMs)],
          ["Критических ошибок", String(stats.criticalErrors)],
        ].map(([label, value]) => (
          <Card variant="outlined" sx={{ flex: 1 }} key={label}>
            <CardContent>
              <Typography color="text.secondary">{label}</Typography>
              <Typography variant="h5">{value}</Typography>
            </CardContent>
          </Card>
        ))}
      </Stack>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 3 }}>
        <Typography component="h3" variant="h6" sx={{ mb: 2 }}>Динамика результата</Typography>
        {recent.length === 0 ? (
          <Typography color="text.secondary">Оценённых тренировок пока нет.</Typography>
        ) : (
          <Stack spacing={1.5}>
            {[...recent].reverse().map((item) => (
              <Box key={item.id}>
                <Stack direction="row" justifyContent="space-between" spacing={2}>
                  <Typography variant="body2">{formatDate(item.created_at)}</Typography>
                  <Typography variant="body2">{item.score.toFixed(0)} / {item.max_score.toFixed(0)}</Typography>
                </Stack>
                <LinearProgress
                  variant="determinate"
                  value={item.max_score > 0 ? Math.min(100, (item.score / item.max_score) * 100) : 0}
                  sx={{ mt: 0.5, height: 7, borderRadius: 4 }}
                />
              </Box>
            ))}
          </Stack>
        )}
      </Paper>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", overflow: "hidden" }}>
        <Box sx={{ p: 2 }}>
          <Typography component="h3" variant="h6">Последние тренировки</Typography>
        </Box>
        <Table size="small" aria-label="Последние тренировки оператора">
          <TableHead>
            <TableRow>
              <TableCell>Дата</TableCell>
              <TableCell>Баллы</TableCell>
              <TableCell>Реакция</TableCell>
              <TableCell>Ошибки</TableCell>
              <TableCell>Критические</TableCell>
              <TableCell>Статус</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recent.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6}>Нет результатов</TableCell>
              </TableRow>
            ) : recent.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{formatDate(item.created_at)}</TableCell>
                <TableCell>{item.score.toFixed(0)} / {item.max_score.toFixed(0)}</TableCell>
                <TableCell>{formatReactionTime(item.reaction_time_ms)}</TableCell>
                <TableCell>{item.error_count}</TableCell>
                <TableCell>{item.critical_error_count}</TableCell>
                <TableCell>{item.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
