import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: { baseURL: "http://127.0.0.1:8001", trace: "retain-on-failure" },
  webServer: {
    command: `${process.env.FLAVORBUDDY_PYTHON || "../.venv/bin/python"} ../scripts/e2e_server.py`,
    url: "http://127.0.0.1:8001/health/ready",
    reuseExistingServer: false,
    timeout: 60000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["Pixel 5"], viewport: { width: 360, height: 780 } },
    },
  ],
});
