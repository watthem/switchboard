import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    browserName: "chromium",
    viewport: { width: 1280, height: 800 },
    colorScheme: "dark",
  },
});
