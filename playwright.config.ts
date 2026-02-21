import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    browserName: "chromium",
    viewport: { width: 1280, height: 800 },
    colorScheme: "dark",
  },
  webServer: {
    command:
      "SWITCHBOARD_API_KEY=demo-key .venv/bin/uvicorn switchboard.app:app --port 59237",
    port: 59237,
    reuseExistingServer: true,
    timeout: 10_000,
  },
});
