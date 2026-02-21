import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import path from "path";

const SCREENSHOTS_DIR = path.resolve(__dirname, "..", "docs", "assets", "screenshots");

test.describe("Switchboard Dashboard Screenshots", () => {
  test.beforeAll(async () => {
    // Seed demo data so the dashboard has agents to show
    try {
      const root = path.resolve(__dirname, "..");
      execSync(".venv/bin/python3 scripts/seed-demo-data.py", {
        cwd: root,
        env: { ...process.env, SWITCHBOARD_API_KEY: "demo-key" },
        stdio: "pipe",
      });
    } catch (e) {
      console.log("Seed script output:", (e as any).stdout?.toString());
      console.error("Seed script error:", (e as any).stderr?.toString());
    }
  });

  test("fleet dashboard overview", async ({ page }) => {
    await page.goto("http://localhost:59237/dashboard");
    await page.waitForTimeout(1500); // wait for API calls + render

    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/fleet-dashboard.png`,
      fullPage: true,
    });
  });

  test("agent detail panel", async ({ page }) => {
    await page.goto("http://localhost:59237/dashboard");
    await page.waitForTimeout(1000);

    // Click on the first agent card to open detail panel
    const agentCard = page.locator(".agent-card").first();
    if (await agentCard.isVisible()) {
      await agentCard.click();
      await page.waitForTimeout(800);
    }

    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/agent-detail.png`,
      fullPage: true,
    });
  });

  test("health endpoint", async ({ page }) => {
    await page.goto("http://localhost:59237/health");
    await page.waitForTimeout(500);

    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/health-endpoint.png`,
    });
  });
});
