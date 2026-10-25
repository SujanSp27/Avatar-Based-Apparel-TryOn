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
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";

// Transport/UI contracts only. Controlled responses never claim model quality.
test("refresh resumes the same job and reports its actual failure without another POST", async ({
  page,
}) => {
  await page.route("**/api/tryon/availability", (route) =>
    route.fulfill({
      json: {
        available: true,
        reason: null,
        backend: "test transport",
        nativeResolution: [576, 864],
      },
    }),
  );
  let posts = 0;
  let jobId = "";
  let failed = false;
  await page.route("**/api/tryon", async (route) => {
    posts += 1;
    expect(route.request().headers().prefer).toBe("respond-async");
    jobId = route.request().headers()["idempotency-key"];
    await route.fulfill({
      status: 202,
      json: {
        jobId,
        status: "processing",
        statusUrl: `/api/tryon/jobs/${jobId}`,
      },
    });
  });
  await page.route("**/api/tryon/jobs/*", async (route) => {
    expect(route.request().url().split("/").pop()).toBe(jobId);
    await route.fulfill({
      json: failed
        ? {
            jobId,
            status: "failed",
            error: {
              code: "vton_garment_fidelity_failed",
              message: "The uploaded stripes were lost.",
            },
          }
        : {
            jobId,
            status: "processing",
            elapsedSeconds: 38,
            progress: { stage: "generating", completed: 7, total: 50 },
          },
    });
  });
  await page.goto("/tryon");
  await page.getByRole("button", { name: "Try sample photos" }).click();
  await page
    .getByRole("button", { name: "Generate try-on", exact: true })
    .click();
  await expect(page.getByTestId("job-progress")).toContainText("step 7 of 50");
  await page.reload();
  await expect(page.getByTestId("job-progress")).toContainText("step 7 of 50");
  expect(posts).toBe(1);
  failed = true;
  await expect(page.getByRole("alert")).toContainText(
    "The uploaded stripes were lost.",
  );
  await expect(page.getByTestId("photo-result")).toHaveCount(0);
  expect(
    await page.evaluate(() => localStorage.getItem("form-fit-last-job")),
  ).toBeNull();
  await page.reload();
  await expect(page.getByTestId("job-progress")).toHaveCount(0);
  expect(posts).toBe(1);
});

test("a recovered job cannot present an overlay as a successful neural result", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem(
      "form-fit-last-job",
      "00000000-0000-4000-8000-000000000001",
    ),
  );
  await page.route("**/api/tryon/jobs/*", (route) =>
    route.fulfill({
      json: {
        jobId: "00000000-0000-4000-8000-000000000001",
        status: "success",
        result: { mode: "2d", renderingMethod: "overlay" },
      },
    }),
  );
  await page.goto("/tryon");
  await expect(page.getByRole("alert")).toContainText(
    "did not return a pretrained try-on result",
  );
  await expect(page.getByTestId("photo-result")).toHaveCount(0);
});

test("a recovered real FASHN result loads its actual PNG and original comparison", async ({
  page,
}) => {
  const artifact = path.resolve(
    "../experiments/results-redesign/navy-tee/live-result.json",
  );
  test.skip(
    !existsSync(artifact),
    "Optional retained local inference artifact is unavailable.",
  );
  const result = JSON.parse(readFileSync(artifact, "utf8")).result;
  // Historical production URLs are now owner-protected. Replay retained bytes
  // only inside this test; do not reopen public access to old private images.
  await page.route(`**${result.previewUrl}*`, (route) =>
    route.fulfill({
      path: path.join(path.dirname(artifact), "after.png"),
      contentType: "image/png",
    }),
  );
  await page.route(`**${result.originalUrl}*`, (route) =>
    route.fulfill({
      path: path.join(path.dirname(artifact), "original.png"),
      contentType: "image/png",
    }),
  );
  expect(result.renderingMethod).toBe("pretrained-vton");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const jobId = "00000000-0000-4000-8000-000000000002";
  await page.addInitScript(
    (id) => localStorage.setItem("form-fit-last-job", id),
    jobId,
  );
  // Replay the saved *real* result for a viewer contract check; no new inference.
  await page.route("**/api/tryon/jobs/*", (route) =>
    route.fulfill({
      json: {
        jobId,
        status: "success",
        result,
      },
    }),
  );
  await page.goto("/tryon");
  const viewer = page.getByTestId("viewer");
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveAttribute("src", result.previewUrl);
  await expect(
    viewer.getByRole("img", { name: "Original person photo", exact: true }),
  ).toHaveAttribute("src", result.originalUrl);
  await page.getByRole("button", { name: "Slider", exact: true }).click();
  await page
    .getByRole("slider", { name: "Before and after comparison slider" })
    .fill("75");
  await page.getByRole("button", { name: "Side by side", exact: true }).click();
  await expect(viewer.locator(".compare-stage")).toHaveClass(/side/);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    accessibility.violations.map((v) => ({
      id: v.id,
      targets: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
  await page.getByRole("button", { name: "Inspect details" }).click();
  await page
    .getByRole("dialog")
    .getByRole("slider", { name: /Zoom/ })
    .fill("2");
  await expect(page.getByRole("dialog").getByRole("img")).toHaveCSS(
    "max-width",
    "none",
  );
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Inspect details" }),
  ).toBeFocused();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download render" }).click();
  expect((await download).suggestedFilename()).toBe("formfit-tryon.png");
  await page.screenshot({
    path: "../experiments/frontend-studio/tryon-retained-result.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(page.getByTestId("recommended-size")).toHaveCount(0);
  expect(errors).toEqual([]);
});
