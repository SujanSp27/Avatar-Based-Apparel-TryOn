import { signInForTest } from "./session-fixture";
import { test, expect } from "@playwright/test";

let accountPassword = "";
test.beforeEach(async ({ page }) => {
  accountPassword = await signInForTest(page);
});
test.afterEach(async ({ page }) => {
  await page.request.delete("/api/v1/profile", {
    data: { password: accountPassword },
  });
});

test("recovers automatically and offers retry without a page reload", async ({
  page,
}) => {
  let ready = false;
  let requests = 0;
  await page.route("**/api/tryon/availability", (route) => {
    requests++;
    return route.fulfill({
      json: {
        available: ready,
        reason: ready
          ? null
          : "Preparing your online try-on service automatically.",
        connectionState: ready ? "ready" : "connecting",
        automaticConnection: true,
      },
    });
  });
  await page.goto("/tryon");
  await expect(page.getByTestId("model-status")).toContainText(
    "Preparing try-on",
  );
  await expect(
    page.getByRole("button", { name: "Retry connection" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Try sample photos" }).click();
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeDisabled();
  ready = true;
  await expect(page.getByTestId("model-status")).toContainText(
    "Ready to try on",
  );
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeEnabled();
  expect(requests).toBeGreaterThan(1);
});

test("losing the API clears readiness and retries automatically", async ({
  page,
}) => {
  let offline = false;
  await page.clock.install();
  await page.route("**/api/tryon/availability", (route) =>
    offline
      ? route.abort()
      : route.fulfill({
          json: {
            available: true,
            reason: null,
          },
        }),
  );
  await page.goto("/tryon");
  await expect(page.getByTestId("model-status")).toContainText(
    "Ready to try on",
  );
  await page.getByRole("button", { name: "Try sample photos" }).click();
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeEnabled();
  offline = true;
  await page.clock.fastForward(16000);
  await expect(page.getByTestId("model-status")).toContainText(
    "Temporarily unavailable",
  );
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeDisabled();
  offline = false;
  await page.clock.fastForward(4000);
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("photo-only app offers model categories and never exposes avatar controls", async ({
  page,
}) => {
  await page.goto("/tryon");
  await expect(
    page.getByLabel("Garment category").locator("option"),
  ).toHaveCount(11);
  await page.getByLabel("Garment category").selectOption("dress");
  await expect(page.getByLabel("Try-on mode")).toHaveCount(0);
  await expect(page.getByLabel("Height in cm")).toHaveCount(0);
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(
    page.getByText("Your computer’s GPU is never used.", { exact: false }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

// Six-metric real sizing is covered in studio.spec.ts.

test("failed recovery exposes retry and recovers without losing uploads", async ({
  page,
}) => {
  let ready = false;
  let retries = 0;
  const status = () => ({
    available: ready,
    connectionState: ready ? "ready" : "recovery_delayed",
    displayState: ready ? "Ready" : "Temporarily unavailable",
    reason: ready
      ? null
      : "Colab has not answered its runtime check. The existing request is preserved.",
  });
  await page.route("**/api/tryon/availability", (route) =>
    route.fulfill({ json: status() }),
  );
  await page.route("**/api/tryon/retry", (route) => {
    retries++;
    ready = true;
    return route.fulfill({ status: 202, json: status() });
  });
  await page.goto("/tryon");
  await page.getByRole("button", { name: "Try sample photos" }).click();
  await expect(page.getByTestId("model-status")).toContainText(
    "Temporarily unavailable",
  );
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByAltText("Selected garment conditioning image"),
  ).toBeVisible();
  expect(retries).toBe(1);
});

test("a hanging health request expires instead of leaving stale readiness", async ({
  page,
}) => {
  await page.clock.install();
  let hang = false;
  await page.route("**/api/tryon/availability", async (route) => {
    if (hang) return; // No response: exercise the real eight-second timeout.
    await route.fulfill({ json: { available: true, reason: null } });
  });
  await page.goto("/tryon");
  await expect(page.getByTestId("model-status")).toHaveAttribute(
    "data-ready",
    "true",
  );
  hang = true;
  await page.clock.fastForward(4000);
  await page.clock.fastForward(9000);
  await expect(page.getByTestId("model-status")).toContainText(
    "Temporarily unavailable",
  );
  await expect(page.getByTestId("model-status")).toHaveAttribute(
    "data-ready",
    "false",
  );
  await expect(
    page.getByRole("button", { name: "Retry connection" }),
  ).toBeEnabled();
});
