import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";

import {
  formatActiveStatus,
  formatDateTime,
  formatFailureReason,
  formatLoginResult,
} from "../../entities/operator/lib/format";
import {
  useOperatorLoginHistoryQuery,
  useOperatorQuery,
  useOperatorStatsQuery,
  usePatchOperatorMutation,
  useResetOperatorPasswordMutation,
} from "../../entities/operator/model/queries";
import { ApiClientError } from "../../shared/api/client";
import { ErrorView } from "../../shared/ui/ErrorView";
import { LoadingView } from "../../shared/ui/LoadingView";

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.message;
  }
  return "Операция не выполнена";
}

interface TemporaryPasswordDialogProps {
  password: string | null;
  onClose: () => void;
}

function TemporaryPasswordDialog({
  password,
  onClose,
}: TemporaryPasswordDialogProps): JSX.Element {
  return (
    <Dialog open={password !== null} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Временный пароль</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Alert severity="warning">
            Пароль показывается только один раз. Передайте его оператору по безопасному каналу.
          </Alert>
          <TextField label="Пароль" value={password ?? ""} InputProps={{ readOnly: true }} fullWidth />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} variant="contained">
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  loading: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  loading,
  onClose,
  onConfirm,
}: ConfirmDialogProps): JSX.Element {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Typography>{message}</Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>
          Отмена
        </Button>
        <Button onClick={onConfirm} variant="contained" disabled={loading}>
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function AdminOperatorDetailPage(): JSX.Element {
  const { operatorId } = useParams();
  const resolvedOperatorId = operatorId ?? "";
  const [historyLimit, setHistoryLimit] = useState(10);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [confirmActiveOpen, setConfirmActiveOpen] = useState(false);
  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(null);

  const operatorQuery = useOperatorQuery(resolvedOperatorId);
  const statsQuery = useOperatorStatsQuery(resolvedOperatorId);
  const historyQuery = useOperatorLoginHistoryQuery(
    resolvedOperatorId,
    historyLimit,
    historyOffset,
  );
  const patchMutation = usePatchOperatorMutation(resolvedOperatorId);
  const resetMutation = useResetOperatorPasswordMutation(resolvedOperatorId);

  if (operatorId === undefined) {
    return <ErrorView title="Оператор не найден" message="Некорректный адрес страницы." />;
  }

  if (operatorQuery.isLoading) {
    return <LoadingView message="Загружаем карточку оператора" />;
  }

  if (operatorQuery.isError || operatorQuery.data === undefined) {
    return (
      <ErrorView
        message={getErrorMessage(operatorQuery.error)}
        actionLabel="К списку"
        onAction={() => {
          window.history.back();
        }}
      />
    );
  }

  const operator = operatorQuery.data;
  const nextActiveState = !operator.is_active;

  return (
    <Stack spacing={3}>
      <Stack
        alignItems={{ xs: "stretch", sm: "center" }}
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        spacing={2}
      >
        <Box>
          <Button component={RouterLink} to="/admin/operators" sx={{ mb: 1 }}>
            К списку
          </Button>
          <Typography component="h2" variant="h4">
            {operator.full_name}
          </Typography>
          <Typography color="text.secondary">@{operator.username}</Typography>
        </Box>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <Button
            variant="outlined"
            onClick={() => {
              resetMutation.mutate(undefined, {
                onSuccess: (response) => {
                  setTemporaryPassword(response.temporary_password);
                },
              });
            }}
            disabled={resetMutation.isPending}
          >
            Сбросить пароль
          </Button>
        </Stack>
      </Stack>

      {patchMutation.error !== null ? (
        <Alert severity="error">{getErrorMessage(patchMutation.error)}</Alert>
      ) : null}
      {resetMutation.error !== null ? (
        <Alert severity="error">{getErrorMessage(resetMutation.error)}</Alert>
      ) : null}

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 3 }}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2}>
          <Stack spacing={1}>
            <Typography component="h3" variant="h6">
              Сведения
            </Typography>
            <Typography>Username: {operator.username}</Typography>
            <Typography>ФИО: {operator.full_name}</Typography>
            <Chip
              label={formatActiveStatus(operator.is_active)}
              color={operator.is_active ? "success" : "default"}
              sx={{ width: "fit-content" }}
            />
          </Stack>
          <Stack alignItems={{ xs: "flex-start", md: "flex-end" }} spacing={1}>
            <Typography component="label" sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              Активен
              <Switch
                checked={operator.is_active}
                onChange={() => setConfirmActiveOpen(true)}
                inputProps={{ "aria-label": "Изменить активность оператора" }}
              />
            </Typography>
          </Stack>
        </Stack>
      </Paper>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">Успешных входов</Typography>
            <Typography component="p" variant="h4">
              {statsQuery.isLoading ? "..." : (statsQuery.data?.successful_count ?? 0)}
            </Typography>
          </CardContent>
        </Card>
        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">Последний успешный вход</Typography>
            <Typography component="p" variant="h6">
              {statsQuery.isLoading
                ? "Загрузка"
                : formatDateTime(statsQuery.data?.last_successful_login_at ?? null)}
            </Typography>
          </CardContent>
        </Card>
      </Stack>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider" }}>
        <Box sx={{ p: 2 }}>
          <Typography component="h3" variant="h6">
            История входов
          </Typography>
        </Box>
        {historyQuery.isLoading ? (
          <LoadingView message="Загружаем историю входов" />
        ) : historyQuery.isError || historyQuery.data === undefined ? (
          <Box sx={{ p: 2 }}>
            <ErrorView
              message={getErrorMessage(historyQuery.error)}
              actionLabel="Повторить"
              onAction={() => void historyQuery.refetch()}
            />
          </Box>
        ) : (
          <>
            <TableContainer>
              <Table aria-label="История входов оператора">
                <TableHead>
                  <TableRow>
                    <TableCell>Дата</TableCell>
                    <TableCell>Результат</TableCell>
                    <TableCell>Причина ошибки</TableCell>
                    <TableCell>IP</TableCell>
                    <TableCell>User-Agent</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {historyQuery.data.items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5}>
                        <Typography color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                          История входов пуста
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ) : (
                    historyQuery.data.items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{formatDateTime(item.occurred_at)}</TableCell>
                        <TableCell>{formatLoginResult(item.success)}</TableCell>
                        <TableCell>{formatFailureReason(item.failure_reason)}</TableCell>
                        <TableCell>{item.ip_address ?? "Нет данных"}</TableCell>
                        <TableCell>{item.user_agent ?? "Нет данных"}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={historyQuery.data.total}
              labelRowsPerPage="Строк на странице"
              page={Math.floor(historyOffset / historyLimit)}
              rowsPerPage={historyLimit}
              rowsPerPageOptions={[10, 20, 50]}
              onPageChange={(_, page) => {
                setHistoryOffset(page * historyLimit);
              }}
              onRowsPerPageChange={(event) => {
                const nextLimit = Number(event.target.value);
                setHistoryLimit(nextLimit);
                setHistoryOffset(0);
              }}
            />
          </>
        )}
      </Paper>

      <ConfirmDialog
        open={confirmActiveOpen}
        title={nextActiveState ? "Активировать оператора" : "Отключить оператора"}
        message={
          nextActiveState
            ? "Оператор снова сможет войти в систему."
            : "Оператор потеряет доступ, а его refresh tokens будут отозваны."
        }
        confirmLabel={nextActiveState ? "Активировать" : "Отключить"}
        loading={patchMutation.isPending}
        onClose={() => setConfirmActiveOpen(false)}
        onConfirm={() => {
          patchMutation.mutate(
            { is_active: nextActiveState },
            {
              onSuccess: () => {
                setConfirmActiveOpen(false);
              },
            },
          );
        }}
      />
      <TemporaryPasswordDialog
        password={temporaryPassword}
        onClose={() => setTemporaryPassword(null)}
      />
    </Stack>
  );
}
