import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const adminUsername = process.env.E2E_ADMIN_USERNAME ?? "e2e-admin";
const adminPassword =
  process.env.E2E_ADMIN_PASSWORD ?? "change-me-e2e-admin-password";
const operatorUsername = process.env.E2E_OPERATOR_USERNAME ?? `e2e-operator-${Date.now()}`;
const operatorPassword =
  process.env.E2E_OPERATOR_PASSWORD ?? "change-me-e2e-operator-password";
const operatorFullName = "E2E Operator";

async function login(page: Page, username: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Имя пользователя").fill(username);
  await page.getByLabel("Пароль").fill(password);
  await page.getByRole("button", { name: "Войти" }).click();
}

async function logout(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Выйти" }).click();
  await expect(page.getByRole("heading", { name: "Вход" })).toBeVisible();
}

async function createOperator(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { name: "Операторы" })).toBeVisible();
  await page.getByRole("button", { name: "Создать оператора" }).click();
  await page.getByLabel("Имя пользователя").fill(operatorUsername);
  await page.getByLabel("ФИО").fill(operatorFullName);
  await page.getByLabel("Пароль").fill(operatorPassword);
  await page.getByRole("button", { name: "Создать" }).click();
  await expect(page.getByText(operatorUsername)).toBeVisible();
}

async function openOperatorDetail(page: Page): Promise<void> {
  await page.goto("/admin/operators");
  await page.getByLabel("Username").fill(operatorUsername);
  await page.getByText(operatorUsername).click();
  await expect(page.getByRole("heading", { name: operatorFullName })).toBeVisible();
}

async function openBoilerDemo(page: Page): Promise<void> {
  await page.goto("/operator/simulators");
  await expect(page.getByRole("heading", { name: "Тренажёры" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Котёл с двумя насосами" })).toBeVisible();
  await page.getByRole("link", { name: "Открыть" }).click();
  await expect(page.getByRole("heading", { name: "Котёл с двумя насосами" })).toBeVisible();
}

function composeLogs(): string {
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
  return execFileSync("docker", ["compose", "logs", "backend", "frontend"], {
    cwd: repoRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

test.describe.configure({ mode: "serial" });

test("MVP happy path uses authoritative simulation state", async ({ page }) => {
  await login(page, adminUsername, adminPassword);
  await expect(page).toHaveURL(/\/admin\/operators/u);
  await createOperator(page);
  await logout(page);

  await login(page, operatorUsername, operatorPassword);
  await expect(page).toHaveURL(/\/operator\/simulators/u);
  await logout(page);

  await login(page, adminUsername, adminPassword);
  await openOperatorDetail(page);
  await expect(page.getByText("Успешно").first()).toBeVisible();
  await logout(page);

  await login(page, operatorUsername, operatorPassword);
  await openBoilerDemo(page);
  await page.getByRole("button", { name: "Начать тренировку" }).click();
  await expect(page).toHaveURL(/\/operator\/sessions\/[0-9a-f-]+/u);
  await expect(page.getByRole("heading", { name: "Сессия тренировки" })).toBeVisible();
  await expect(page.getByText("Статус: stopped").first()).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Сессия тренировки" })).toBeVisible();
  await expect(page.getByText("Статус: stopped").first()).toBeVisible();

  await page.getByRole("button", { name: "Запустить steam_supply_pump" }).click();
  await expect(page.getByText("Статус: running").first()).toBeVisible();
  await expect(page.getByRole("cell", { name: "Принята" }).first()).toBeVisible();

  await page.getByRole("button", { name: "Остановить steam_supply_pump" }).click();
  await expect(page.getByText("Статус: stopped").first()).toBeVisible();

  await page.getByRole("button", { name: "Завершить сессию" }).click();
  await expect(page).toHaveURL(/\/operator\/simulators/u);
  await expect(page.getByRole("heading", { name: "Тренажёры" })).toBeVisible();
});

test("forbidden routes are blocked by role guards", async ({ page }) => {
  await login(page, adminUsername, adminPassword);
  await page.goto("/operator/simulators");
  await expect(page.getByRole("heading", { name: "Недостаточно прав" })).toBeVisible();
  await logout(page);

  await login(page, operatorUsername, operatorPassword);
  await page.goto("/admin/operators");
  await expect(page.getByRole("heading", { name: "Недостаточно прав" })).toBeVisible();
});

test("simulation unavailable is shown without local state changes", async ({ page }) => {
  await login(page, operatorUsername, operatorPassword);
  await openBoilerDemo(page);
  await page.route("**/api/v1/simulation-sessions", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "SIMULATION_SERVICE_UNAVAILABLE",
            message: "Сервис моделирования недоступен",
            details: {},
          },
        }),
      });
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Начать тренировку" }).click();
  await expect(page.getByText("Сервис моделирования сейчас недоступен.")).toBeVisible();
});

test("service logs do not expose e2e secrets", async () => {
  const logs = composeLogs();
  expect(logs).not.toContain(adminPassword);
  expect(logs).not.toContain(operatorPassword);
  expect(logs).not.toContain("access_token");
  expect(logs).not.toContain("refresh_token");
});
