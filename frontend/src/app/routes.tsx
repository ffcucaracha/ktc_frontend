import { useMemo } from "react";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { useCurrentUserQuery } from "../features/auth/model/queries";
import { homePathForRole } from "../features/auth/lib/routes";
import { AdminOperatorsPage } from "../pages/admin-operators/AdminOperatorsPage";
import { AdminOperatorDetailPage } from "../pages/admin-operator-detail/AdminOperatorDetailPage";
import { LoginPage } from "../pages/login/LoginPage";
import { OperatorSessionPage } from "../pages/operator-session/OperatorSessionPage";
import { OperatorSimulatorDetailPage } from "../pages/operator-simulator-detail/OperatorSimulatorDetailPage";
import { OperatorSimulatorsPage } from "../pages/operator-simulators/OperatorSimulatorsPage";
import { ErrorView } from "../shared/ui/ErrorView";
import { LoadingView } from "../shared/ui/LoadingView";
import { AppShell } from "./AppShell";

interface ProtectedRouteProps {
  allowedRoles: Array<"admin" | "operator">;
  children: JSX.Element;
}

function RootRedirect(): JSX.Element {
  const { data: user, isLoading } = useCurrentUserQuery();

  if (isLoading) {
    return <LoadingView message="Проверяем сессию" />;
  }
  if (user === undefined) {
    return <Navigate to="/login" replace />;
  }
  return <Navigate to={homePathForRole(user.role)} replace />;
}

function ProtectedRoute({ allowedRoles, children }: ProtectedRouteProps): JSX.Element {
  const { data: user, isLoading } = useCurrentUserQuery();

  if (isLoading) {
    return <LoadingView message="Проверяем доступ" />;
  }
  if (user === undefined) {
    return <Navigate to="/login" replace />;
  }
  if (!allowedRoles.includes(user.role)) {
    return (
      <ErrorView
        title="Недостаточно прав"
        message="Этот раздел недоступен для вашей роли."
      />
    );
  }
  return children;
}

function createRouter() {
  return createBrowserRouter([
    {
      path: "/",
      element: <AppShell />,
      errorElement: (
        <AppShell>
          <ErrorView message="Страница не найдена или временно недоступна." />
        </AppShell>
      ),
      children: [
        { index: true, element: <RootRedirect /> },
        { path: "login", element: <LoginPage /> },
        {
          path: "admin/operators",
          element: (
            <ProtectedRoute allowedRoles={["admin"]}>
              <AdminOperatorsPage />
            </ProtectedRoute>
          ),
        },
        {
          path: "admin/operators/:operatorId",
          element: (
            <ProtectedRoute allowedRoles={["admin"]}>
              <AdminOperatorDetailPage />
            </ProtectedRoute>
          ),
        },
        {
          path: "operator/simulators",
          element: (
            <ProtectedRoute allowedRoles={["operator"]}>
              <OperatorSimulatorsPage />
            </ProtectedRoute>
          ),
        },
        {
          path: "operator/simulators/:simulatorId",
          element: (
            <ProtectedRoute allowedRoles={["operator"]}>
              <OperatorSimulatorDetailPage />
            </ProtectedRoute>
          ),
        },
        {
          path: "operator/sessions/:sessionId",
          element: (
            <ProtectedRoute allowedRoles={["operator"]}>
              <OperatorSessionPage />
            </ProtectedRoute>
          ),
        },
        {
          path: "*",
          element: <ErrorView title="Страница не найдена" message="Такого раздела нет." />,
        },
      ],
    },
  ]);
}

export function AppRouter(): JSX.Element {
  const router = useMemo(() => createRouter(), []);
  return <RouterProvider router={router} />;
}
