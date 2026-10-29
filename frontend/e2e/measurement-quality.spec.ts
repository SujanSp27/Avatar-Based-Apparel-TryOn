import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";

test.use({ actionTimeout: 15000 });
const evidence = "../experiments/torso-validation";
mkdirSync(evidence, { recursive: true });

test("retry keeps photo and height, then actual CPU extraction feeds owner-scoped sizing", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/measure");
  await page.getByRole("button", { name: "Try a sample", exact: true }).click();
  await page.getByLabel("Height in centimeters").fill("180");
  const photo = page.getByRole("img", {
    name: "Your uploaded full-body photo",
    exact: true,
  });
  await expect(photo).toBeVisible();
  await expect
    .poll(() => photo.evaluate((node: HTMLCanvasElement) => node.width))
    .toBeGreaterThan(300);
  const originalPixels = await photo.evaluate((node: HTMLCanvasElement) =>
    node.toDataURL(),
  );
  let calls = 0;
  await page.route("**/api/v1/measurements/extract", async (route) => {
    calls++;
    if (calls === 1)
      return route.fulfill({
        status: 422,
        json: {
          error: {
            code: "torso_segmentation_failed",
            message:
              "Pose detected, but the central torso outline is missing. Use a clear contrasting background or enter tape measurements.",
          },
        },
      });
    return route.continue();
  });
  await page
    .getByRole("button", { name: "Extract measurements", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("central torso outline");
  await expect(page.getByLabel("Height in centimeters")).toHaveValue("180");
  expect(
    await photo.evaluate((node: HTMLCanvasElement) => node.toDataURL()),
  ).toBe(originalPixels);
  const extracted = page.waitForResponse(
    (r) => r.url().endsWith("/measurements/extract") && r.status() === 200,
  );
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  const scan = await (await extracted).json();
  expect(scan.provenance.method).toBe("landmark-silhouette-projection-v4");
  expect(scan.geometry.height_cm).toBe(180);
  expect(scan.quality.requires_manual_review).toEqual([]);
  await expect(
    page.getByRole("img", { name: /all 33 pose landmarks/ }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Find my size", exact: true })
    .last()
    .click();
  const sizing = page.waitForResponse((r) =>
    r.url().endsWith("/sizing/recommend"),
  );
  await page.getByRole("button", { name: "Find my size", exact: true }).click();
  const sized = await sizing;
  expect(sized.status()).toBe(200);
  expect(sized.request().postDataJSON().measurement_id).toBe(
    scan.measurement_id,
  );
  expect(sized.request().postDataJSON().measurements).toBeUndefined();
  await expect(page.getByTestId("recommended-size")).toBeVisible();
  // Do not leave the disposable guest scan behind.
  expect(
    (
      await page.request.delete(`/api/v1/measurements/${scan.measurement_id}`)
    ).status(),
  ).toBe(204);
  expect(calls).toBe(2);
  expect(errors).toEqual([]);
});

test("partial scan keeps skeleton, exposes uncertainty and requires each flagged correction", async ({
  page,
}) => {
  // Controlled UI contract, not an inference-quality claim. Server gating has
  // separate API regression coverage with real ownership and chart calculations.
  const landmarks = Array.from({ length: 33 }, () => [0.5, 0.15, 0, 0.99]);
  const scan = {
    measurement_id: "pose_" + "a".repeat(32),
    scale_factor: 0.2,
    measurements: {
      shoulder_width: 44.2,
      chest_circumference: null,
      waist_circumference: 120,
      hip_circumference: 95.5,
      thigh_circumference: 56,
      inseam_length: 79,
    },
    landmarks_normalized: landmarks,
    annotated_image_url: "/unused-test-annotation.png",
    geometry: { image_size: [1000, 1500], height_cm: 172 },
    warnings: ["Review clothing-dependent estimates with a tape measure."],
    quality: {
      estimates_only: true,
      minimum_key_landmark_visibility: 0.99,
      status: "review_required",
      requires_manual_review: ["chest_circumference", "waist_circumference"],
      metrics: {
        chest_circumference: {
          status: "unavailable",
          reason: "arms_overlap_torso",
          requires_manual_review: true,
          message:
            "Arms overlap the visible torso outline; enter this tape measurement.",
        },
        waist_circumference: {
          status: "review_required",
          reason: "wide_clothing_outline",
          requires_manual_review: true,
          message:
            "Clothing or body shape may explain the wide outline; confirm with a tape measure.",
        },
      },
    },
  };
  await page.route("**/api/v1/measurements/extract", (route) =>
    route.fulfill({ json: scan }),
  );
  let sizingCalls = 0;
  await page.route("**/api/v1/sizing/recommend", (route) => {
    sizingCalls++;
    return route.fulfill({
      status: 422,
      json: { error: { code: "fixture", message: "UI contract only" } },
    });
  });
  await page.goto("/measure");
  await page.getByRole("button", { name: "Try a sample", exact: true }).click();
  await page
    .getByRole("button", { name: "Extract measurements", exact: true })
    .click();
  await expect(
    page.getByRole("img", { name: /all 33 pose landmarks/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("status", { name: "Measurement quality" }),
  ).toContainText("Some measurements need review");
  await expect(
    page.getByRole("button", { name: "Save measurements", exact: true }),
  ).toBeDisabled();
  const sizeLink = page
    .getByRole("link", { name: "Find my size", exact: true })
    .last();
  await expect(sizeLink).toHaveAttribute("aria-disabled", "true");
  const chestCard = page
    .locator(".metric-card")
    .filter({ hasText: "Chest circumference" });
  await expect(chestCard.locator(".metric-value")).toContainText("Unavailable");
  await page
    .getByRole("button", { name: "Edit Chest circumference", exact: true })
    .click();
  await page.getByLabel("Chest circumference in centimeters").fill("96.5");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(sizeLink).toHaveAttribute("aria-disabled", "true");
  await page.setViewportSize({ width: 375, height: 812 });
  await page.screenshot({
    path: `${evidence}/partial-scan-mobile.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  // Navigation via the sidebar cannot bypass the same quality gate.
  await page.getByRole("link", { name: "Size", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Find my size", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("Photo measurements need review:", { exact: false }),
  ).toContainText("Waist circumference");
  await page.getByRole("button", { name: "Edit values", exact: true }).click();
  await page.getByLabel("Waist circumference", { exact: true }).fill("84.5");
  await expect(
    page.getByRole("button", { name: "Find my size", exact: true }),
  ).toBeEnabled();
  expect(sizingCalls).toBe(0);
});

test("failed re-extraction clears stale measurements while retaining the selected input", async ({
  page,
}) => {
  await page.goto("/measure");
  await page.getByRole("button", { name: "Try a sample", exact: true }).click();
  const response = page.waitForResponse((r) =>
    r.url().endsWith("/measurements/extract"),
  );
  await page
    .getByRole("button", { name: "Extract measurements", exact: true })
    .click();
  const extracted = await response;
  expect(extracted.status()).toBe(200);
  const scan = await extracted.json();
  await expect(
    page.getByRole("img", { name: /all 33 pose landmarks/ }),
  ).toBeVisible();
  await page.route("**/api/v1/measurements/extract", (route) =>
    route.fulfill({
      status: 422,
      json: {
        error: {
          code: "low_visibility",
          message: "Keep both hips visible and retry.",
        },
      },
    }),
  );
  await page
    .getByRole("button", { name: "Extract measurements", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Keep both hips visible");
  await expect(
    page.getByRole("img", {
      name: "Your uploaded full-body photo",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: /all 33 pose landmarks/ }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Save measurements", exact: true }),
  ).toBeDisabled();
  expect(
    (
      await page.request.delete(`/api/v1/measurements/${scan.measurement_id}`)
    ).status(),
  ).toBe(204);
});

test("unavailable thigh stays explicit through inches and manual correction", async ({
  page,
}) => {
  const scan = {
    measurement_id: "pose_" + "b".repeat(32),
    scale_factor: 0.2,
    measurements: {
      shoulder_width: 40,
      chest_circumference: 98,
      waist_circumference: 92,
      hip_circumference: 96,
      thigh_circumference: null,
      inseam_length: 80,
    },
    landmarks_normalized: Array.from({ length: 33 }, () => [0.5, 0.5, 0, 0.99]),
    landmark_presence: Array.from({ length: 33 }, (_, i) =>
      i === 29 ? 0.1 : 0.99,
    ),
    annotated_image_url: "/unused-test-annotation.png",
    warnings: ["Circumferences are estimates."],
    geometry: { image_size: [600, 1000], height_cm: 160 },
    quality: {
      estimates_only: true,
      minimum_key_landmark_visibility: 0.99,
      status: "review_required",
      requires_manual_review: ["thigh_circumference"],
      metrics: {
        thigh_circumference: {
          status: "unavailable",
          reason: "ambiguous_thigh",
          requires_manual_review: true,
          message:
            "Both upper-thigh boundaries cannot be distinguished reliably. Enter a tape measurement.",
        },
      },
    },
  };
  await page.route("**/api/v1/measurements/extract", (route) =>
    route.fulfill({ json: scan }),
  );
  await page.goto("/measure");
  await page.getByRole("button", { name: "Try a sample", exact: true }).click();
  await page
    .getByRole("button", { name: "Extract measurements", exact: true })
    .click();
  const thigh = page
    .locator(".metric-card")
    .filter({ hasText: "Thigh circumference" });
  await expect(thigh.locator(".metric-value")).toHaveText("Unavailable");
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(thigh.locator(".metric-value")).toBeVisible();
  await expect(thigh).toContainText("upper-thigh boundaries");
  await expect(
    page
      .locator(".metric-card")
      .filter({ hasText: "Chest circumference" })
      .locator(".metric-value"),
  ).toContainText("98.0");
  await page.getByLabel("Display measurements in").selectOption("in");
  await expect(thigh.locator(".metric-value")).toHaveText("Unavailable");
  await expect(
    page.getByRole("button", { name: "Save measurements", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Edit Thigh circumference", exact: true })
    .click();
  await page.getByLabel("Thigh circumference in inches").fill("20");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByLabel("Display measurements in").selectOption("cm");
  await expect(thigh.locator(".metric-value")).toContainText("50.8");
  await expect(thigh).toContainText("Manually corrected");
  await expect(
    page.getByRole("button", { name: "Save measurements", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("status", { name: "Measurement quality" }),
  ).toHaveCount(0);
});
