import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";

import { clearAccessToken } from "../src/shared/auth/authStore";
import { server } from "./msw/server";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  clearAccessToken();
  server.resetHandlers();
  window.history.pushState(null, "", "/");
});

afterAll(() => {
  server.close();
});
