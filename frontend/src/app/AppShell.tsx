import { useQueryClient } from "@tanstack/react-query";
import { Box, Button, Container, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { Outlet, useNavigate } from "react-router-dom";

import { currentUserQueryKey, useCurrentUserQuery } from "../features/auth/model/queries";
import { logout } from "../shared/api/auth";

interface AppShellProps {
  children?: ReactNode;
}

export function AppShell({ children }: AppShellProps): JSX.Element {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUserQuery();

  const handleLogout = async (): Promise<void> => {
    try {
      await logout();
    } finally {
      queryClient.removeQueries({ queryKey: currentUserQueryKey });
      navigate("/login", { replace: true });
    }
  };

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <Box
        component="header"
        sx={{
          borderBottom: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
        }}
      >
        <Container maxWidth="lg" sx={{ py: 2 }}>
          <Stack
            alignItems={{ xs: "flex-start", sm: "center" }}
            direction={{ xs: "column", sm: "row" }}
            justifyContent="space-between"
            spacing={2}
          >
            <Stack spacing={0.25}>
              <Typography component="h1" variant="h5">
                Тренажёр оператора
              </Typography>
              {user !== undefined ? (
                <Typography color="text.secondary" variant="body2">
                  {user.full_name} · {user.role === "admin" ? "администратор" : "оператор"}
                </Typography>
              ) : null}
            </Stack>
            {user !== undefined ? (
              <Button variant="outlined" onClick={() => void handleLogout()}>
                Выйти
              </Button>
            ) : null}
          </Stack>
        </Container>
      </Box>

      <Container component="main" maxWidth="lg" sx={{ py: 4 }}>
        {children ?? <Outlet />}
      </Container>
    </Box>
  );
}
