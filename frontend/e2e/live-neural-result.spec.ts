import { test, expect } from "@playwright/test";

// Explicitly opt in with an actual API job ID. No mocked responses, static
// substitutes or implicit inference runs are used by this viewer check.
test("the live neural job survives refresh and displays its actual generated image", async ({
  page,
  request,
}) => {
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
  await page.addInitScript(
    (id) => localStorage.setItem("form-fit-last-job", id!),
    jobId,
  );
  await page.goto("/tryon");
  await page.reload();
  await expect
    .poll(
      async () => {
        const response = await request.get(`/api/tryon/jobs/${jobId}`);
        expect(response.ok()).toBeTruthy();
        const job = await response.json();
        if (job.status === "failed") throw new Error(JSON.stringify(job.error));
        return job.status;
      },
      { timeout: 850000, intervals: [3000] },
    )
    .toBe("success");
  const job = await (await request.get(`/api/tryon/jobs/${jobId}`)).json();
  expect(job.result.renderingMethod).toBe("pretrained-vton");
  expect(job.result.provenance.execution).toBe("online-gpu-only");
  expect(job.result.provenance.localGpuUsed).toBe(false);
  const viewer = page.getByTestId("viewer");
  await expect(viewer).toHaveAttribute("data-loaded", "true", {
    timeout: 30000,
  });
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveAttribute("src", job.result.previewUrl);
  await page.screenshot({
    path: "../experiments/anchored-live-browser-20261015.png",
    fullPage: true,
  });
  await expect(
    viewer.getByRole("img", { name: "Original person photo", exact: true }),
  ).toHaveAttribute("src", job.result.originalUrl);
  await page
    .getByRole("slider", { name: "Before and after comparison slider" })
    .fill("75");
  await page.getByRole("button", { name: "Side by side", exact: true }).click();
  await expect(viewer.locator(".compare-stage")).toHaveClass(/side/);
  expect(posts).toBe(0);
  expect(errors).toEqual([]);
});
