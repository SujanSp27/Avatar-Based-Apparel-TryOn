import { test, expect } from "@playwright/test";

test("connects automatically without a connection button or page reload", async ({page}) => {
  let ready = false;
  let requests = 0;
  await page.route("**/api/health", route => {
    requests++;
    return route.fulfill({json: {status: "ok", vton2d: {
      available: ready, reason: ready ? null : "Preparing your online try-on service automatically.",
      connectionState: ready ? "ready" : "connecting", automaticConnection: true,
    }}});
  });
  await page.goto("/tryon");
  await expect(page.getByTestId("model-status")).toContainText("Preparing try-on");
  await expect(page.getByRole("button", {name: /connect/i})).toHaveCount(0);
  await page.getByRole("button", {name: "Try sample photos"}).click();
  await expect(page.getByRole("button", {name: "Generate try-on", exact:true})).toBeDisabled();
  ready = true;
  await expect(page.getByTestId("model-status")).toContainText("Ready to try on");
  await expect(page.getByRole("button", {name: "Generate try-on", exact:true})).toBeEnabled();
  expect(requests).toBeGreaterThan(1);
});

test("losing the API clears readiness and retries automatically", async ({page}) => {
  let offline = false;
  await page.clock.install();
  await page.route("**/api/health", route => offline ? route.abort() : route.fulfill({json: {
    status: "ok", vton2d: {available: true, reason: null},
  }}));
  await page.goto("/tryon");
  await expect(page.getByTestId("model-status")).toContainText("Ready to try on");
  await page.getByRole("button", {name: "Try sample photos"}).click();
  await expect(page.getByRole("button", {name: "Generate try-on", exact:true})).toBeEnabled();
  offline = true;
  await page.clock.fastForward(16000);
  await expect(page.getByTestId("model-status")).toContainText("Starting the app");
  await expect(page.getByRole("button", {name: "Generate try-on", exact:true})).toBeDisabled();
  offline = false;
  await page.clock.fastForward(4000);
  await expect(page.getByRole("button", {name: "Generate try-on", exact:true})).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("photo-only app offers model categories and never exposes avatar controls", async ({page}) => {
  await page.goto("/tryon");
  await expect(page.getByLabel("Garment category").locator("option")).toHaveCount(11);
  await page.getByLabel("Garment category").selectOption("dress");
  await expect(page.getByLabel("Try-on mode")).toHaveCount(0);
  await expect(page.getByLabel("Height in cm")).toHaveCount(0);
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(page.getByText("Your computer’s GPU is never used.", {exact:false})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

// Six-metric real sizing is covered in studio.spec.ts.
