import { test, expect } from "@playwright/test";

// Explicitly opt in with an actual API job ID. No mocked responses, static
// substitutes or implicit inference runs are used by this viewer check.
test("the live neural job survives refresh and displays its actual generated image", async ({ page, request }) => {
  const jobId = process.env.VTON_LIVE_JOB_ID;
  test.skip(!jobId, "Set VTON_LIVE_JOB_ID to a submitted real inference job.");
  test.setTimeout(900000);
  expect(jobId).toMatch(/^[a-f0-9-]{36}$/);
  let posts = 0;
  const errors: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/api/tryon")) posts += 1;
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript((id) => localStorage.setItem("form-fit-last-job", id!), jobId);
  await page.goto("/");
  await page.reload();
  await expect.poll(async () => {
    const response = await request.get(`/api/tryon/jobs/${jobId}`);
    expect(response.ok()).toBeTruthy();
    const job = await response.json();
    if (job.status === "failed") throw new Error(JSON.stringify(job.error));
    return job.status;
  }, { timeout: 850000, intervals: [3000] }).toBe("success");
  const job = await (await request.get(`/api/tryon/jobs/${jobId}`)).json();
  expect(job.result.renderingMethod).toBe("pretrained-vton");
  expect(job.result.provenance.weights.conditioning).toBe("reference-anchor");
  const viewer = page.getByTestId("viewer");
  await expect(viewer).toHaveAttribute("data-loaded", "true", { timeout: 30000 });
  await expect(viewer.locator("img")).toHaveAttribute("src", job.result.previewUrl);
  await page.screenshot({ path: "../experiments/anchored-live-browser-20261015.png", fullPage: true });
  await page.getByRole("button", { name: "Original", exact: true }).click();
  await expect(viewer.locator("img")).toHaveAttribute("src", job.result.originalUrl);
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await page.getByRole("button", { name: "Try-on", exact: true }).click();
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  expect(posts).toBe(0);
  expect(errors).toEqual([]);
});
