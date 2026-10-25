import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";

test.use({ actionTimeout: 15000 });

const evidence = "../experiments/frontend-studio";
mkdirSync(evidence, { recursive: true });
const metrics: Record<string, string> = {
  "Shoulder width": "44.2",
  "Chest circumference": "94",
  "Waist circumference": "82",
  "Hip circumference": "94",
  "Thigh circumference": "56.3",
  "Inseam length": "78.6",
};
async function checkAccessibility(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    result.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
      help: v.help,
    })),
  ).toEqual([]);
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}

test("guest measurement screen works from mobile to ultrawide, validates uploads and camera denial", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/measure");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "A fit that starts",
  );
  await expect(page.locator(".metric-card")).toHaveCount(6);
  await checkAccessibility(page);
  for (const width of [375, 768, 1440, 3840]) {
    await page.setViewportSize({ width, height: width === 375 ? 812 : 1050 });
    await noOverflow(page);
    if ([375, 1440].includes(width))
      await page.screenshot({
        path: `${evidence}/measure-${width}.png`,
        fullPage: true,
      });
  }
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.getByRole("button", { name: "ft / in", exact: true }).click();
  await page.getByLabel("Height feet").fill("5");
  await page.getByLabel("Height inches").fill("10");
  await page.getByRole("button", { name: "cm", exact: true }).click();
  await expect(page.getByLabel("Height in centimeters")).toHaveValue("177.8");
  await page.getByLabel("Your full-body photo", { exact: true }).setInputFiles({
    name: "bad.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not an image"),
  });
  await expect(page.getByRole("alert")).toContainText("JPEG");
  await page.getByLabel("Your full-body photo", { exact: true }).setInputFiles({
    name: "large.png",
    mimeType: "image/png",
    buffer: Buffer.alloc(10 * 1024 * 1024 + 1),
  });
  await expect(page.getByRole("alert")).toContainText("10 MB");
  await page.evaluate(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      throw new DOMException("Permission denied", "NotAllowedError");
    };
  });
  await page.getByRole("button", { name: "Use your camera" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Use your camera" }),
  ).toBeFocused();
  expect(errors).toEqual([]);
});

test("real six-metric sizing API, chart comparison, unsupported guide and mobile results", async ({
  page,
}) => {
  await page.goto("/sizing");
  for (const [label, value] of Object.entries(metrics))
    await page.getByLabel(label, { exact: true }).fill(value);
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/sizing/recommend") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Find my size", exact: true }).click();
  const data = await (await response).json();
  expect(data.recommended_size).toBe("M");
  expect(data.fit_confidence).toBeCloseTo(100 / (1 + data.minimum_error), 3);
  await expect(page.getByTestId("recommended-size")).toHaveText(
    data.recommended_size,
  );
  await expect(page.locator(".deviation-row")).toHaveCount(
    Object.keys(data.active_weights).length,
  );
  await checkAccessibility(page);
  await page.screenshot({
    path: `${evidence}/sizing-desktop.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: "Size guide", exact: false }).click();
  await expect(page.getByRole("dialog").getByRole("table")).toBeVisible();
  await checkAccessibility(page);
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Size guide", exact: false }),
  ).toBeFocused();
  await page.setViewportSize({ width: 375, height: 812 });
  await noOverflow(page);
  await page.screenshot({
    path: `${evidence}/sizing-mobile.png`,
    fullPage: true,
  });
  await page
    .getByRole("combobox", { name: "Brand", exact: true })
    .selectOption("adidas");
  await expect(
    page.getByText("No verified body chart", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Find my size", exact: true }),
  ).toBeDisabled();
  await expect(page.getByTestId("recommended-size")).toHaveCount(0);
});

test("real account, photo extraction, private history, closet, session rotation and logout", async ({
  page,
  context,
}) => {
  const email = `studio-e2e-${Date.now()}@example.com`;
  const password = "StudioTest-43!secure";
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/signup");
  await page.getByLabel("Your name", { exact: true }).fill("Studio Test");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  await page.getByRole("checkbox", { name: /I accept/ }).check();
  await checkAccessibility(page);
  await page.getByRole("button", { name: "Create your account" }).click();
  await expect(page).toHaveURL(/\/profile$/);
  const cookie = (await context.cookies()).find(
    (c) => c.name === "formfit_refresh",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  await page.getByRole("tab", { name: "Account settings" }).click();
  await page.getByLabel("Default height (cm)").fill("172");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toContainText("Profile updated");
  await page.getByRole("button", { name: "New measurement" }).click();
  await page.getByRole("button", { name: "Try a sample", exact: true }).click();
  const extracted = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/measurements/extract"),
    { timeout: 90000 },
  );
  await page.getByRole("button", { name: "Extract measurements" }).click();
  const response = await extracted;
  expect(response.status()).toBe(200);
  const scan = await response.json();
  expect(scan.landmarks_normalized).toHaveLength(33);
  await expect(
    page.getByRole("img", { name: /all 33 pose landmarks/ }),
  ).toBeVisible();
  for (const [label, value] of Object.entries(metrics)) {
    await page
      .getByRole("button", { name: `Edit ${label}`, exact: true })
      .click();
    await page.getByLabel(`${label} in centimeters`).fill(value);
    await page.getByRole("button", { name: "Save", exact: true }).click();
  }
  await page.getByRole("checkbox", { name: "Landmark skeleton" }).uncheck();
  await expect(
    page.getByRole("img", { name: "Your uploaded full-body photo" }),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: "Landmark skeleton" }).check();
  await page.screenshot({
    path: `${evidence}/measured-desktop.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: "Save measurements" }).click();
  await expect(page.getByRole("status")).toContainText("Measurements saved");
  await page
    .getByRole("link", { name: "Find my size", exact: true })
    .last()
    .click();
  await page.getByRole("button", { name: "Find my size", exact: true }).click();
  await expect(page.getByTestId("recommended-size")).toHaveText("M");
  await page.getByRole("button", { name: "Save to My Closet" }).click();
  await expect(page.getByRole("status")).toContainText("Size saved");
  await page.getByRole("link", { name: "My profile & closet" }).click();
  await expect(page.locator(".scan-history-card")).toHaveCount(1);
  await expect(
    page.getByRole("img", { name: "Private saved scan thumbnail" }),
  ).toBeVisible();
  await checkAccessibility(page);
  await page.screenshot({
    path: `${evidence}/profile-desktop.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 375, height: 812 });
  await noOverflow(page);
  await page.screenshot({
    path: `${evidence}/profile-mobile.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.getByRole("tab", { name: "Measurement history" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "My Closet" })).toBeFocused();
  await expect(page.locator(".closet-size")).toHaveText("M");
  // Simultaneous tabs must rotate the shared HttpOnly cookie without replay revocation.
  const second = await context.newPage();
  await Promise.all([page.reload(), second.goto("/profile")]);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Studio");
  await expect(second.getByRole("heading", { level: 1 })).toContainText(
    "Studio",
  );
  await second.close();
  expect(
    (await context.cookies()).find((c) => c.name === "formfit_refresh")?.value,
  ).not.toBe(cookie?.value);
  const storage = await page.evaluate(() => ({
    ...localStorage,
    ...sessionStorage,
  }));
  expect(JSON.stringify(storage)).not.toMatch(
    /access_token|refresh_token|StudioTest/,
  );
  // A rejected access token invokes the real rotation endpoint, then retries once.
  let rejected = false;
  await page.route("**/api/v1/profile/scans?*", (route) => {
    if (!rejected) {
      rejected = true;
      return route.fulfill({
        status: 401,
        json: { detail: "Expired access token test" },
      });
    }
    return route.continue();
  });
  await page.getByRole("button", { name: "New measurement" }).click();
  // Wait for the lazy route to commit before navigating back. Otherwise React
  // may coalesce both navigations without remounting the profile or fetching.
  await expect(page).toHaveURL(/\/measure$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "A fit that starts",
  );
  await page.getByRole("link", { name: "My profile & closet" }).click();
  await expect(page.locator(".scan-history-card")).toHaveCount(1);
  expect(rejected).toBe(true);
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("button", { name: "Delete scan", exact: true }).click();
  await expect(page.locator(".scan-history-card")).toHaveCount(0);
  await page.getByRole("tab", { name: "My Closet" }).click();
  await page.getByRole("button", { name: "Remove saved size" }).click();
  await expect(page.locator(".closet-card")).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByRole("link", { name: "My profile & closet" }).click();
  await expect(page).toHaveURL(/\/login\?returnTo=/);
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("checkbox", { name: "Remember me" }).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/profile$/);
  expect(
    (await context.cookies()).find((c) => c.name === "formfit_refresh")!
      .expires,
  ).toBeGreaterThan(Date.now() / 1000 + 86400);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  expect(errors).toEqual([]);
});

test("auth validation, protected return URL, reset configuration error and not-found route", async ({
  page,
}) => {
  await page.goto("/profile");
  await expect(page).toHaveURL(/\/login\?returnTo=/);
  await page.getByRole("button", { name: "Forgot password?" }).click();
  const modal = page.getByRole("dialog");
  await modal.getByLabel("Email address").fill("studio-test@example.com");
  await modal.getByRole("button", { name: "Send reset link" }).click();
  await expect(modal.getByRole("alert")).toContainText("not configured");
  await checkAccessibility(page);
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Forgot password?" }),
  ).toBeFocused();
  await page.goto("/signup");
  await page.getByRole("button", { name: "Create your account" }).click();
  await expect(
    page.getByText("Please read and accept the terms."),
  ).toBeVisible();
  await page.getByLabel("Password", { exact: true }).fill("short");
  await page.getByRole("button", { name: "Create your account" }).click();
  await expect(
    page.getByText("Your password must meet all four requirements."),
  ).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await noOverflow(page);
  await page.screenshot({
    path: `${evidence}/signup-mobile.png`,
    fullPage: true,
  });
  await page.goto("/reset-password");
  await expect(page.getByText(/reset link/i).first()).toBeVisible();
  await page.goto("/missing-page");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "in the studio",
  );
});
