import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  // Real inference verification can resume while the local regression suite runs.
  // Separate artifacts prevent one runner from deleting another runner's traces.
  outputDir:
    process.env.VASTRAVIEW_LIVE === "1" ? "test-results-live" : "test-results",
  timeout: 240000,
  expect: { timeout: 15000 },
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    [
      "json",
      {
        outputFile:
          process.env.VASTRAVIEW_LIVE === "1"
            ? "../experiments/browser-live-report.json"
            : "../experiments/browser-test-report.json",
      },
    ],
  ],
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 1050 },
    headless: true,
    launchOptions: { args: ["--disable-gpu"] },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
