import { zodResolver } from "@hookform/resolvers/zod";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
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
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { formatActiveStatus, formatDateTime } from "../../entities/operator/lib/format";
import {
  useCreateOperatorMutation,
  useOperatorStatsQueries,
  useOperatorsQuery,
} from "../../entities/operator/model/queries";
import { ApiClientError } from "../../shared/api/client";
import { ErrorView } from "../../shared/ui/ErrorView";
import { LoadingView } from "../../shared/ui/LoadingView";

const pageSizeOptions = [10, 20, 50];

const createOperatorSchema = z.object({
  username: z.string().min(1, "Введите имя пользователя").max(64),
  full_name: z.string().min(1, "Введите ФИО").max(255),
  password: z
    .string()
    .transform((value) => value.trim())
    .refine((value) => value.length === 0 || value.length >= 8, {
      message: "Минимум 8 символов",
    }),
});

type CreateOperatorForm = z.infer<typeof createOperatorSchema>;

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
          <TextField
            label="Пароль"
            value={password ?? ""}
            InputProps={{ readOnly: true }}
            fullWidth
          />
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

interface CreateOperatorDialogProps {
  open: boolean;
  onClose: () => void;
  onTemporaryPassword: (password: string) => void;
}

function CreateOperatorDialog({
  open,
  onClose,
  onTemporaryPassword,
}: CreateOperatorDialogProps): JSX.Element {
  const mutation = useCreateOperatorMutation();
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<CreateOperatorForm>({
    resolver: zodResolver(createOperatorSchema),
    defaultValues: {
      username: "",
      full_name: "",
      password: "",
    },
  });

  const closeDialog = (): void => {
    reset();
    mutation.reset();
    onClose();
  };

  return (
    <Dialog open={open} onClose={closeDialog} fullWidth maxWidth="sm">
      <DialogTitle>Создать оператора</DialogTitle>
      <DialogContent>
        <Stack
          component="form"
          id="create-operator-form"
          spacing={2}
          sx={{ pt: 1 }}
          onSubmit={(event) => {
            void handleSubmit((values) => {
              const password = values.password.length > 0 ? values.password : undefined;
              mutation.mutate(
                {
                  username: values.username,
                  full_name: values.full_name,
                  password,
                },
                {
                  onSuccess: (response) => {
                    closeDialog();
                    if (response.temporary_password !== null) {
                      onTemporaryPassword(response.temporary_password);
                    }
                  },
                },
              );
            })(event);
          }}
          noValidate
        >
          {mutation.error !== null ? (
            <Alert severity="error">{getErrorMessage(mutation.error)}</Alert>
          ) : null}
          <TextField
            label="Имя пользователя"
            autoComplete="off"
            error={errors.username !== undefined}
            helperText={errors.username?.message}
            disabled={mutation.isPending}
            {...register("username")}
          />
          <TextField
            label="ФИО"
            autoComplete="off"
            error={errors.full_name !== undefined}
            helperText={errors.full_name?.message}
            disabled={mutation.isPending}
            {...register("full_name")}
          />
          <TextField
            label="Пароль"
            type="password"
            autoComplete="new-password"
            error={errors.password !== undefined}
            helperText={errors.password?.message ?? "Оставьте пустым для генерации"}
            disabled={mutation.isPending}
            {...register("password")}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={closeDialog} disabled={mutation.isPending}>
          Отмена
        </Button>
        <Button form="create-operator-form" type="submit" variant="contained" disabled={mutation.isPending}>
          Создать
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function AdminOperatorsPage(): JSX.Element {
  const navigate = useNavigate();
  const [limit, setLimit] = useState(10);
  const [offset, setOffset] = useState(0);
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "inactive">("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(null);

  const operatorsQuery = useOperatorsQuery({
    limit,
    offset,
    username: username.trim() || undefined,
    full_name: fullName.trim() || undefined,
    is_active: activeFilter === "all" ? undefined : activeFilter === "active",
  });
  const operatorList = operatorsQuery.data;
  const operators = operatorList?.items ?? [];
  const statsQueries = useOperatorStatsQueries(operators.map((operator) => operator.id));

  if (operatorsQuery.isLoading) {
    return <LoadingView message="Загружаем операторов" />;
  }

  if (operatorsQuery.isError) {
    return (
      <ErrorView
        message={getErrorMessage(operatorsQuery.error)}
        actionLabel="Повторить"
        onAction={() => void operatorsQuery.refetch()}
      />
    );
  }

  return (
    <Stack spacing={3}>
      <Stack
        alignItems={{ xs: "stretch", sm: "center" }}
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        spacing={2}
      >
        <Box>
          <Typography component="h2" variant="h4">
            Операторы
          </Typography>
          <Typography color="text.secondary">
            Управление доступом операторов и историей входов.
          </Typography>
        </Box>
        <Button variant="contained" onClick={() => setCreateOpen(true)}>
          Создать оператора
        </Button>
      </Stack>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
          <TextField
            label="Username"
            value={username}
            onChange={(event) => {
              setUsername(event.target.value);
              setOffset(0);
            }}
            fullWidth
          />
          <TextField
            label="ФИО"
            value={fullName}
            onChange={(event) => {
              setFullName(event.target.value);
              setOffset(0);
            }}
            fullWidth
          />
          <FormControl fullWidth>
            <InputLabel id="active-filter-label">Статус</InputLabel>
            <Select
              labelId="active-filter-label"
              label="Статус"
              value={activeFilter}
              onChange={(event) => {
                setActiveFilter(event.target.value as "all" | "active" | "inactive");
                setOffset(0);
              }}
            >
              <MenuItem value="all">Все</MenuItem>
              <MenuItem value="active">Активные</MenuItem>
              <MenuItem value="inactive">Отключённые</MenuItem>
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider" }}>
        <TableContainer>
          <Table aria-label="Список операторов">
            <TableHead>
              <TableRow>
                <TableCell>Username</TableCell>
                <TableCell>ФИО</TableCell>
                <TableCell>Статус</TableCell>
                <TableCell align="right">Успешных входов</TableCell>
                <TableCell>Последний вход</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {operators.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                      Операторы не найдены
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                operators.map((operator, index) => {
                  const stats = statsQueries[index]?.data;
                  return (
                    <TableRow
                      hover
                      key={operator.id}
                      onClick={() => navigate(`/admin/operators/${operator.id}`)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          navigate(`/admin/operators/${operator.id}`);
                        }
                      }}
                      role="link"
                      sx={{ cursor: "pointer" }}
                      tabIndex={0}
                    >
                      <TableCell>{operator.username}</TableCell>
                      <TableCell>{operator.full_name}</TableCell>
                      <TableCell>
                        <Chip
                          label={formatActiveStatus(operator.is_active)}
                          color={operator.is_active ? "success" : "default"}
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">
                        {statsQueries[index]?.isLoading ? "..." : (stats?.successful_count ?? 0)}
                      </TableCell>
                      <TableCell>
                        {statsQueries[index]?.isLoading
                          ? "Загрузка"
                          : formatDateTime(stats?.last_successful_login_at ?? null)}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={operatorList?.total ?? 0}
          labelRowsPerPage="Строк на странице"
          page={Math.floor(offset / limit)}
          rowsPerPage={limit}
          rowsPerPageOptions={pageSizeOptions}
          onPageChange={(_, page) => {
            setOffset(page * limit);
          }}
          onRowsPerPageChange={(event) => {
            const nextLimit = Number(event.target.value);
            setLimit(nextLimit);
            setOffset(0);
          }}
        />
      </Paper>

      <CreateOperatorDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onTemporaryPassword={setTemporaryPassword}
      />
      <TemporaryPasswordDialog
        password={temporaryPassword}
        onClose={() => setTemporaryPassword(null)}
      />
    </Stack>
  );
}
