import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";

import { homePathForRole } from "../../features/auth/lib/routes";
import { currentUserQueryKey, useCurrentUserQuery } from "../../features/auth/model/queries";
import { getCurrentUser, login } from "../../shared/api/auth";
import { ApiClientError } from "../../shared/api/client";
import type { User } from "../../shared/api/types";
import { LoadingView } from "../../shared/ui/LoadingView";

const schema = z.object({
  username: z.string().min(1, "Введите имя пользователя"),
  password: z.string().min(1, "Введите пароль"),
});

type LoginForm = z.infer<typeof schema>;

const e2eUsers: Array<LoginForm & { label: string }> = [
  {
    label: "Войти как администратор",
    username: "e2e-admin",
    password: "change-me-e2e-admin-password",
  },
  {
    label: "Войти как оператор",
    username: "e2e-operator",
    password: "change-me-e2e-operator-password",
  },
];

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.message;
  }
  return "Не удалось выполнить вход";
}

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: currentUser, isLoading } = useCurrentUserQuery();
  const {
    formState: { errors },
    handleSubmit,
    register,
  } = useForm<LoginForm>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  const mutation = useMutation({
    mutationFn: async (payload: LoginForm): Promise<User> => {
      await login(payload);
      return getCurrentUser();
    },
    onSuccess: (user) => {
      queryClient.setQueryData(currentUserQueryKey, user);
      navigate(homePathForRole(user.role), { replace: true });
    },
  });

  useEffect(() => {
    if (currentUser !== undefined) {
      navigate(homePathForRole(currentUser.role), { replace: true });
    }
  }, [currentUser, navigate]);

  if (isLoading) {
    return <LoadingView message="Проверяем сессию" />;
  }
  if (currentUser !== undefined) {
    return <Navigate to={homePathForRole(currentUser.role)} replace />;
  }

  return (
    <Box
      sx={{
        display: "grid",
        minHeight: { xs: "calc(100vh - 112px)", md: "calc(100vh - 128px)" },
        placeItems: "center",
      }}
    >
      <Paper
        component="section"
        elevation={0}
        sx={{
          width: "100%",
          maxWidth: 440,
          border: "1px solid",
          borderColor: "divider",
          p: { xs: 3, sm: 4 },
        }}
      >
        <Stack spacing={3}>
          <Stack spacing={1}>
            <Typography component="h2" variant="h4">
              Вход
            </Typography>
            <Typography color="text.secondary">
              Используйте имя пользователя и пароль оператора или администратора.
            </Typography>
          </Stack>

          {mutation.error !== null ? (
            <Alert severity="error" role="alert">
              {loginErrorMessage(mutation.error)}
            </Alert>
          ) : null}

          <Stack
            component="form"
            spacing={2}
            onSubmit={(event) => {
              void handleSubmit((values) => mutation.mutate(values))(event);
            }}
            noValidate
          >
            <TextField
              label="Имя пользователя"
              autoComplete="username"
              error={errors.username !== undefined}
              helperText={errors.username?.message}
              disabled={mutation.isPending}
              {...register("username")}
            />
            <TextField
              label="Пароль"
              type="password"
              autoComplete="current-password"
              error={errors.password !== undefined}
              helperText={errors.password?.message}
              disabled={mutation.isPending}
              {...register("password")}
            />
            <Button type="submit" variant="contained" disabled={mutation.isPending} size="large">
              {mutation.isPending ? "Входим" : "Войти"}
            </Button>
          </Stack>

          {import.meta.env.DEV ? (
            <>
              <Divider />
              <Stack spacing={1.5}>
                <Typography variant="subtitle2">Тестовый вход</Typography>
                <Stack spacing={1}>
                  {e2eUsers.map((user) => (
                    <Button
                      key={user.username}
                      type="button"
                      variant="outlined"
                      disabled={mutation.isPending}
                      onClick={() => {
                        mutation.mutate({
                          username: user.username,
                          password: user.password,
                        });
                      }}
                      sx={{ justifyContent: "space-between", flex: 1 }}
                    >
                      <Box component="span">{user.label}</Box>
                    </Button>
                  ))}
                </Stack>
              </Stack>
            </>
          ) : null}
        </Stack>
      </Paper>
    </Box>
  );
}
