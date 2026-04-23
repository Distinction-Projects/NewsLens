const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3101",
    browserName: "chromium",
    headless: true,
  },
  webServer: {
    command: "npx next dev -p 3101",
    url: "http://localhost:3101/news",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
