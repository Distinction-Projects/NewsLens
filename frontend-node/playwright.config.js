const { defineConfig } = require("@playwright/test");

const frontendServer = {
  command: "npx next dev -p 3101",
  url: "http://localhost:3101/news",
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
};

const startFastApi = process.env.PLAYWRIGHT_START_FASTAPI === "1";
const webServer = startFastApi
  ? [
      {
        command:
          "cd .. && ./.venv/bin/python -m uvicorn src.api.fastapi_app:app --host 127.0.0.1 --port 9000",
        url: "http://127.0.0.1:9000/health/database",
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
      frontendServer,
    ]
  : frontendServer;

module.exports = defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3101",
    browserName: "chromium",
    headless: true,
  },
  webServer,
});
