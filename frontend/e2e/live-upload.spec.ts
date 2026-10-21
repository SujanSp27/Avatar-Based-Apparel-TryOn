import { test, expect } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

// This is intentionally opt-in: normal browser tests must not send photos or
// start GPU jobs. Resume an interrupted job with live-neural-result.spec.ts.
test("a fresh upload displays its actual Colab result", async ({
  page,
  request,
}) => {
  test.skip(
    process.env.VTON_LIVE_UPLOAD !== "1",
    "Explicit private Colab inference opt-in required.",
  );
  test.setTimeout(180000);
  const output = resolve(
    process.env.VTON_LIVE_REPORT_DIR ||
      "../experiments/live-balanced-upload-20261020",
  );
  // Refuse to overwrite a previous submission, even if a test was interrupted.
  mkdirSync(output, { recursive: false });
  const person = resolve("../data/raw/studio-person.jpg");
  const garment = resolve("../data/raw/vton-official/garment-rhude.jpg");
  const sha256 = (file: string) =>
    createHash("sha256").update(readFileSync(file)).digest("hex");
  const inputs = {
    personSha256: sha256(person),
    garmentSha256: sha256(garment),
  };
  const errors: string[] = [];
  let posts = 0;
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/api/tryon")) posts++;
  });
  await page.goto("/tryon");
  await expect(page.getByTestId("model-status")).toHaveAttribute(
    "data-ready",
    "true",
    { timeout: 60000 },
  );
  await page
    .getByLabel("Your person photo", { exact: true })
    .setInputFiles(person);
  await page.getByLabel("Your garment", { exact: true }).setInputFiles(garment);
  await page.getByLabel("Garment category").selectOption("t-shirt");
  await page
    .getByLabel("Garment photo type", { exact: true })
    .selectOption("flat-lay");
  const started = Date.now();
  const submitted = page.waitForResponse(
    (r) => r.request().method() === "POST" && r.url().endsWith("/api/tryon"),
  );
  await page
    .getByRole("button", { name: "Generate try-on", exact: true })
    .click();
  const response = await submitted;
  expect(response.status()).toBe(202);
  const submission = await response.json();
  const jobId = submission.jobId;
  expect(jobId).toMatch(/^[a-f0-9-]{36}$/);
  writeFileSync(
    resolve(output, "submission.json"),
    JSON.stringify(
      {
        jobId,
        submittedAt: new Date(started).toISOString(),
        inputs,
      },
      null,
      2,
    ),
  );
  const viewer = page.getByTestId("viewer");
  await expect(viewer).toHaveAttribute("data-loaded", "true", {
    timeout: 100000,
  });
  const browserSeconds = (Date.now() - started) / 1000;
  const jobResponse = await request.get(`/api/tryon/jobs/${jobId}`);
  expect(jobResponse.ok()).toBeTruthy();
  const job = await jobResponse.json();
  writeFileSync(resolve(output, "job.json"), JSON.stringify(job, null, 2));
  expect(job.status).toBe("success");
  const result = job.result;
  expect(result.provenance.execution).toBe("online-gpu-only");
  expect(result.provenance.localGpuUsed).toBe(false);
  expect(result.renderingMethod).toBe("pretrained-vton");
  const diagnostics = result.provenance.weights;
  expect(diagnostics.steps).toBe(10);
  expect(diagnostics.modelResolution).toEqual([504, 756]);
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveAttribute("src", result.previewUrl);
  const image = await request.get(result.previewUrl);
  expect(image.ok()).toBeTruthy();
  writeFileSync(resolve(output, "tryon-2d.png"), await image.body());
  writeFileSync(
    resolve(output, "timing.json"),
    JSON.stringify(
      {
        jobId,
        runId: result.runId,
        browserSeconds,
        pipelineSeconds: result.timingSeconds,
        gpuSeconds: diagnostics.inferenceSeconds,
        targetSeconds: 30,
        timingTargetMet: browserSeconds <= 30,
        freshGeneration: true,
        visualAcceptance: "pending inspection",
        inputs,
      },
      null,
      2,
    ),
  );
  await page.screenshot({
    path: resolve(output, "browser.png"),
    fullPage: true,
  });
  await expect(
    viewer.getByRole("img", { name: "Original person photo", exact: true }),
  ).toHaveAttribute("src", result.originalUrl);
  await page
    .getByRole("slider", { name: "Before and after comparison slider" })
    .fill("75");
  await page.getByRole("button", { name: "Side by side", exact: true }).click();
  await expect(viewer.locator(".compare-stage")).toHaveClass(/side/);
  expect(posts).toBe(1);
  expect(errors).toEqual([]);
  // Keep timing and image evidence even when the timing target is missed.
  expect(
    browserSeconds,
    "Fresh upload to loaded browser image",
  ).toBeLessThanOrEqual(30);
});
