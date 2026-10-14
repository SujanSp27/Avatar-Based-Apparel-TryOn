import { test, expect } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

// Transport/UI contracts only. Controlled responses never claim model quality.
test("refresh resumes the same job and reports its actual failure without another POST", async ({ page }) => {
  let posts = 0;
  let jobId = "";
  let failed = false;
  await page.route("**/api/tryon", async (route) => {
    posts += 1;
    expect(route.request().headers().prefer).toBe("respond-async");
    jobId = route.request().headers()["idempotency-key"];
    await route.fulfill({ status: 202, json: { jobId, status: "processing", statusUrl: `/api/tryon/jobs/${jobId}` } });
  });
  await page.route("**/api/tryon/jobs/*", async (route) => {
    expect(route.request().url().split("/").pop()).toBe(jobId);
    await route.fulfill({ json: failed
      ? { jobId, status: "failed", error: { code: "vton_garment_fidelity_failed", message: "The uploaded stripes were lost." } }
      : { jobId, status: "processing", elapsedSeconds: 38, progress: { stage: "generating", completed: 7, total: 50 } },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Try sample photos" }).click();
  await page.getByRole("button", { name: "Generate try-on", exact: true }).click();
  await expect(page.getByTestId("job-progress")).toContainText("step 7 of 50");
  await page.reload();
  await expect(page.getByTestId("job-progress")).toContainText("step 7 of 50");
  expect(posts).toBe(1);
  failed = true;
  await expect(page.getByRole("alert")).toContainText("The uploaded stripes were lost.");
  await expect(page.getByTestId("photo-result")).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("form-fit-last-job"))).toBeNull();
  await page.reload();
  await expect(page.getByTestId("job-progress")).toHaveCount(0);
  expect(posts).toBe(1);
});

test("a recovered job cannot present an overlay as a successful neural result", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("form-fit-last-job", "00000000-0000-4000-8000-000000000001"));
  await page.route("**/api/tryon/jobs/*", (route) => route.fulfill({ json: {
    jobId: "00000000-0000-4000-8000-000000000001", status: "success",
    result: { mode: "2d", renderingMethod: "overlay" },
  } }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("did not return a pretrained try-on result");
  await expect(page.getByTestId("photo-result")).toHaveCount(0);
});

test("a recovered real CatVTON result loads its actual PNG and original comparison", async ({ page }) => {
  const artifact = path.resolve("../data/processed/04360792-ad1f-4ec2-8ab7-1255eb8cecc0/result.json");
  test.skip(!existsSync(artifact), "Optional retained local inference artifact is unavailable.");
  const result = JSON.parse(readFileSync(artifact, "utf8"));
  expect(result.renderingMethod).toBe("pretrained-vton");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const jobId = "00000000-0000-4000-8000-000000000002";
  await page.addInitScript((id) => localStorage.setItem("form-fit-last-job", id), jobId);
  // Replay the saved *real* result for a viewer contract check; no new inference.
  await page.route("**/api/tryon/jobs/*", (route) => route.fulfill({ json: {
    jobId, status: "success", result,
  } }));
  await page.goto("/");
  const viewer = page.getByTestId("viewer");
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await expect(viewer.locator("img")).toHaveAttribute("src", result.previewUrl);
  await page.getByRole("button", { name: "Original", exact: true }).click();
  await expect(viewer.locator("img")).toHaveAttribute("src", result.originalUrl);
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await page.getByRole("button", { name: "Try-on", exact: true }).click();
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await expect(page.getByTestId("recommended-size")).toHaveCount(0);
  expect(errors).toEqual([]);
});
