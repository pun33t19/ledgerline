import { defineConfig, devices } from "@playwright/test";

// Starts the real backend (`ledgerline ui`) serving the built app, with a known token for the test.
const PORT = Number(process.env.LEDGERLINE_E2E_PORT ?? 8781);
export const TOKEN = "playwright-test-token";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `cd .. && LEDGERLINE_UI_TOKEN=${TOKEN} uv run ledgerline ui --port ${PORT} --no-browser`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
