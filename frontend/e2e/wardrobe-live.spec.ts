import { test, expect, request } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

// Read already completed private trials. This test never submits inference and
// does not establish visual approval. Do not run concurrently with the evaluator
// because both preserve the same rotating evaluation-account cookies.
test("saved wardrobe trials render and download their real private outputs", async ({
  page,
  context,
}) => {
  test.skip(
    process.env.VASTRAVIEW_LIVE !== "1",
    "Opt-in real private trial check",
  );
  const session = path.resolve("../.runtime/wardrobe-evaluation-session.json");
  await context.addCookies(JSON.parse(readFileSync(session, "utf8")).cookies);
  const errors: string[] = [];
  let submissions = 0;
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/api/tryon")) submissions++;
  });
  try {
    for (const id of ["edit-a59f077d", "edit-4245ab7f"]) {
      const folder = path.resolve(
        `../experiments/wardrobe-neutral/cases/${id}/studio`,
      );
      const trial = JSON.parse(
        readFileSync(path.join(folder, "trial.json"), "utf8"),
      );
      const saved = JSON.parse(
        readFileSync(path.join(folder, "job.json"), "utf8"),
      );
      await page.goto(`/tryon?job=${trial.jobId}`);
      const viewer = page.getByTestId("viewer");
      await expect(viewer).toHaveAttribute("data-loaded", "true");
      await expect(
        viewer.getByRole("img", {
          name: "Generated virtual try-on",
          exact: true,
        }),
      ).toHaveAttribute("src", saved.result.previewUrl);
      const response = await page.request.get(saved.result.previewUrl);
      expect(response.status()).toBe(200);
      expect(response.headers()["cache-control"]).toBe("no-store");
      expect(
        createHash("sha256")
          .update(await response.body())
          .digest("hex"),
      ).toBe(trial.outputSha256);
      await viewer.getByRole("button", { name: "Slider", exact: true }).click();
      await viewer.getByRole("slider").fill("65");
      await viewer
        .getByRole("button", { name: "Side by side", exact: true })
        .click();
      await viewer.getByRole("button", { name: "Inspect details" }).click();
      await expect(
        page
          .getByRole("dialog")
          .getByRole("img", {
            name: "Actual garment reference used for this result",
          }),
      ).toHaveAttribute("src", saved.result.garmentUrl);
      await page.keyboard.press("Escape");
      const downloadEvent = page.waitForEvent("download");
      await viewer.getByRole("link", { name: "Download render" }).click();
      const download = await downloadEvent;
      expect(
        createHash("sha256")
          .update(readFileSync((await download.path())!))
          .digest("hex"),
      ).toBe(trial.outputSha256);
      await page.setViewportSize({ width: 375, height: 812 });
      await viewer.screenshot({ path: path.join(folder, "live-mobile.png") });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.setViewportSize({ width: 1440, height: 1050 });
      await viewer.screenshot({ path: path.join(folder, "live-desktop.png") });
      await page.reload();
      await expect(viewer).toHaveAttribute("data-loaded", "true");
      const guest = await request.newContext({
        baseURL: "http://127.0.0.1:5173",
      });
      try {
        expect((await guest.get(saved.result.previewUrl)).status()).toBe(401);
      } finally {
        await guest.dispose();
      }
    }
    expect(submissions).toBe(0);
    expect(errors).toEqual([]);
  } finally {
    await context.storageState({ path: session });
  }
});
