import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { request } from "@playwright/test";

const backendReadyUrl =
  process.env.E2E_BACKEND_READY_URL ?? "http://localhost:8000/health/ready";
const frontendUrl = process.env.E2E_BASE_URL ?? "http://localhost:5173";
const adminPassword =
  process.env.E2E_ADMIN_PASSWORD ?? "change-me-e2e-admin-password";

async function waitForOk(url: string, label: string): Promise<void> {
  const deadline = Date.now() + 60_000;
  const context = await request.newContext();
  try {
    let lastError = "";
    while (Date.now() < deadline) {
      try {
        const response = await context.get(url, { timeout: 2_000 });
        if (response.ok()) {
          return;
        }
        lastError = `${response.status()} ${response.statusText()}`;
      } catch (error) {
        lastError = error instanceof Error ? error.message : "unknown error";
      }
      await new Promise((resolveTimer) => {
        setTimeout(resolveTimer, 500);
      });
    }
    throw new Error(`${label} is not ready: ${lastError}`);
  } finally {
    await context.dispose();
  }
}

function seedAdmin(): void {
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
  execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "-e",
      `E2E_ADMIN_PASSWORD=${adminPassword}`,
      "backend",
      ".venv/bin/python",
      "-m",
      "app.commands.seed_e2e_admin",
    ],
    {
      cwd: repoRoot,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
}

export default async function globalSetup(): Promise<void> {
  await waitForOk(backendReadyUrl, "backend");
  await waitForOk(frontendUrl, "frontend");
  seedAdmin();
}
