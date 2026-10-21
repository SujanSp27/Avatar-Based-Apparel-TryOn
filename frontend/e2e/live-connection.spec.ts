import { test, expect } from "@playwright/test";

test("existing private Colab connects without user-facing connection controls", async ({ page, request }) => {
  test.skip(process.env.LIVE_COLAB_CONNECTION !== "1", "Requires the user's existing Colab runtime");
  await expect.poll(async () => {
    const response = await request.get("/api/health");
    return (await response.json()).vton2d.available;
  }, { timeout: 120000, intervals: [3000] }).toBe(true);
  const health = await (await request.get("/api/health")).json();
  expect(health.vton2d.localGpuUsed).toBe(false);
  expect(health.vton2d.automaticConnection).toBe(true);
  await page.goto("/tryon");
  await expect(page.getByTestId("model-status")).toContainText("Ready to try on");
  await expect(page.getByRole("button", { name: /connect/i })).toHaveCount(0);
  await page.getByRole("button", { name: "Try sample photos" }).click();
  await expect(page.getByRole("button", { name: "Generate try-on", exact: true })).toBeEnabled();
  await page.screenshot({ path: "../experiments/automatic-colab-ready.png", fullPage: true });
  // Connection verification must not submit an extra inference job.
});
