import { defineConfig, devices } from "@playwright/test";

/**
 * E2E runs against a live stack: FastAPI on :8000 (TEST database recommended) and Next on :3000.
 * `npm run e2e` starts both unless E2E_BASE_URL points at an already running deployment.
 */
const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  use: { baseURL: base, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, grep: /@mobile/ },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : [
        {
          command: "cd ../backend && .venv/bin/uvicorn app.main:app --port 8000",
          url: "http://localhost:8000/api/health",
          reuseExistingServer: true,
          timeout: 60_000,
        },
        { command: "npm run start", url: base, reuseExistingServer: true, timeout: 120_000 },
      ],
});
