import {
  Alert,
  Box,
  Chip,
  Divider,
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

import type { AiModelInfo } from "../../entities/ai-model/api/types";
import { useAiModelsQuery } from "../../entities/ai-model/model/queries";
import { ApiClientError } from "../../shared/api/client";
import { ErrorView } from "../../shared/ui/ErrorView";
import { LoadingView } from "../../shared/ui/LoadingView";

function errorMessage(error: unknown): string {
  return error instanceof ApiClientError ? error.message : "Не удалось загрузить сведения о моделях";
}

function percent(value: number | undefined): string {
  return value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

function formatImportance(value: number): string {
  return `${value.toFixed(2)}%`;
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <Paper variant="outlined" sx={{ p: 2, minWidth: 135, flex: 1 }}>
      <Typography color="text.secondary" variant="caption">
        {label}
      </Typography>
      <Typography variant="h6">{value}</Typography>
    </Paper>
  );
}

function ModelCard({ model }: { model: AiModelInfo }): JSX.Element {
  const metrics = model.validation_metrics;
  const totalRows = model.dataset_rows ?? (model.training_rows ?? 0) + (model.validation_rows ?? 0);
  const topFeatures = model.top_features ?? [];
  const maxImportance = topFeatures[0]?.importance ?? 0;

  return (
    <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 3 }}>
      <Stack spacing={3}>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          justifyContent="space-between"
          alignItems={{ xs: "flex-start", sm: "center" }}
          spacing={1}
        >
          <Box>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
              <Typography component="h3" variant="h5">
                {model.model_version}
              </Typography>
              {model.active ? <Chip label="Активная модель" color="success" size="small" /> : null}
              {!model.artifact_exists ? <Chip label="Файл модели не найден" color="warning" size="small" /> : null}
            </Stack>
            <Typography color="text.secondary" variant="body2" sx={{ mt: 0.5 }}>
              {model.target ?? "ERROR_IN_NEXT_10_SECONDS"}
              {model.horizon_seconds !== undefined ? ` · горизонт ${model.horizon_seconds} с` : ""}
            </Typography>
          </Box>
          <Paper variant="outlined" sx={{ px: 2.5, py: 1.5 }}>
            <Typography color="text.secondary" variant="caption">
              Порог срабатывания
            </Typography>
            <Typography variant="h5">
              {model.threshold === undefined ? "—" : `${Math.round(model.threshold * 100)}%`}
            </Typography>
          </Paper>
        </Stack>

        <Divider />

        <Box>
          <Typography variant="subtitle1" sx={{ mb: 1.5 }}>
            Датасет
          </Typography>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} flexWrap="wrap">
            <Metric label="Всего строк" value={totalRows > 0 ? totalRows.toLocaleString("ru-RU") : "—"} />
            <Metric
              label="Обучающая выборка"
              value={model.training_rows?.toLocaleString("ru-RU") ?? "—"}
            />
            <Metric
              label="Валидационная выборка"
              value={model.validation_rows?.toLocaleString("ru-RU") ?? "—"}
            />
            <Metric
              label="Сессий"
              value={model.dataset_sessions?.toLocaleString("ru-RU") ?? "—"}
            />
          </Stack>
          <Typography color="text.secondary" variant="body2" sx={{ mt: 1.5 }}>
            Источник: {model.dataset_path ?? model.data_provenance ?? "метаданные старой версии не содержат путь к датасету"}
          </Typography>
        </Box>

        <Box>
          <Typography variant="subtitle1" sx={{ mb: 1.5 }}>
            Метрики на валидации
          </Typography>
          {metrics === undefined ? (
            <Alert severity="info">
              Для этой сохранённой версии метрики не записывались в JSON. Они появятся после следующего переобучения новым скриптом.
            </Alert>
          ) : (
            <>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} flexWrap="wrap">
                <Metric label="Accuracy" value={percent(metrics.accuracy)} />
                <Metric label="Precision" value={percent(metrics.precision)} />
                <Metric label="Recall" value={percent(metrics.recall)} />
                <Metric label="F1" value={percent(metrics.f1)} />
              </Stack>
              <Typography color="text.secondary" variant="body2" sx={{ mt: 1.5 }}>
                TP {metrics.tp ?? "—"} · FP {metrics.fp ?? "—"} · TN {metrics.tn ?? "—"} · FN {metrics.fn ?? "—"}
              </Typography>
            </>
          )}
        </Box>

        <Box>
          <Typography variant="subtitle1" sx={{ mb: 1.5 }}>
            Самые влиятельные признаки
          </Typography>
          {topFeatures.length === 0 ? (
            <Typography color="text.secondary">В метаданных нет feature importance.</Typography>
          ) : (
            <Stack spacing={1.5}>
              {topFeatures.map((feature) => {
                const normalized = maxImportance > 0 ? (feature.importance / maxImportance) * 100 : 0;
                return (
                  <Box key={feature.name}>
                    <Stack direction="row" justifyContent="space-between" spacing={2}>
                      <Typography variant="body2" sx={{ wordBreak: "break-word" }}>
                        {feature.name}
                      </Typography>
                      <Typography color="text.secondary" variant="body2">
                        {formatImportance(feature.importance)}
                      </Typography>
                    </Stack>
                    <LinearProgress variant="determinate" value={normalized} sx={{ mt: 0.5, height: 7, borderRadius: 1 }} />
                  </Box>
                );
              })}
            </Stack>
          )}
        </Box>

        <Box>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            Файлы
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Метаданные</TableCell>
                <TableCell>CatBoost</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              <TableRow>
                <TableCell>{model.metadata_file}</TableCell>
                <TableCell>{model.artifact_file}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Box>
      </Stack>
    </Paper>
  );
}

export function AdminAiModelsPage(): JSX.Element {
  const modelsQuery = useAiModelsQuery();

  if (modelsQuery.isLoading) {
    return <LoadingView message="Загружаем результаты обучения" />;
  }
  if (modelsQuery.isError) {
    return (
      <ErrorView
        title="Результаты обучения недоступны"
        message={errorMessage(modelsQuery.error)}
        actionLabel="Повторить"
        onAction={() => void modelsQuery.refetch()}
      />
    );
  }

  const models = modelsQuery.data ?? [];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h2" variant="h4">
          Результаты обучения AI
        </Typography>
        <Typography color="text.secondary">
          Сохранённые версии CatBoost-модели риска: порог, качество, объём данных и признаки, которые сильнее всего влияют на прогноз.
        </Typography>
      </Box>

      {models.length === 0 ? (
        <Alert severity="info">
          В каталоге ai-service/models пока нет сохранённых JSON-метаданных моделей.
        </Alert>
      ) : (
        models.map((model) => <ModelCard key={model.model_version} model={model} />)
      )}
    </Stack>
  );
}
