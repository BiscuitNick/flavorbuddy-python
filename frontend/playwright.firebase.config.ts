import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e-firebase",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8001", trace: "retain-on-failure" },
  webServer: {
    command: `${process.env.FLAVORBUDDY_PYTHON || "../.venv/bin/python"} ../scripts/e2e_server.py`,
    url: "http://127.0.0.1:8001/health/ready",
    timeout: 60000,
    env: {
      DJANGO_ENV: "test",
      FIREBASE_PROJECT_ID: "demo-flavorbuddy",
      FIREBASE_API_KEY: "fake-key",
      FIREBASE_AUTH_DOMAIN: "demo-flavorbuddy.firebaseapp.com",
      FIREBASE_APP_ID: "demo-app",
      FIREBASE_AUTH_EMULATOR_HOST: "127.0.0.1:9099",
      LOCAL_AUTH_ENABLED: "false",
    },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["Pixel 5"], viewport: { width: 360, height: 780 } },
    },
  ],
});
