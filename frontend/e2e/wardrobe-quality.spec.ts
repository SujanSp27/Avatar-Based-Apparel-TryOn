import { test, expect } from "@playwright/test";
import { authenticatedSuite } from "./session-fixture";
import { readFileSync } from "node:fs";
import path from "node:path";

authenticatedSuite(test);

test("catalog distinguishes category support from reviewed garment quality", async ({
  page,
}) => {
  await page.goto("/catalog");
  await page.getByRole("searchbox").fill("Forest-green polo");
  await page.getByRole("button", { name: /Forest-green polo/ }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Individual garment quality has not yet passed",
  );
});

test("result inspection uses the saved garment reference and preserves the compact comparison", async ({
  page,
}) => {
  const evidence = path.resolve(
    "../experiments/wardrobe-curation/cases/edit-a59f077d/studio",
  );
  const job = JSON.parse(readFileSync(path.join(evidence, "job.json"), "utf8"));
  const result = {
    ...job.result,
    originalUrl: "/wardrobe-fixture/before.png",
    previewUrl: "/wardrobe-fixture/after.png",
    garmentUrl: "/wardrobe-fixture/garment.png",
  };
  await page.route("**/api/tryon/availability", (route) =>
    route.fulfill({ json: { available: true } }),
  );
  await page.route("**/api/tryon/jobs/*", (route) =>
    route.fulfill({ json: { ...job, result } }),
  );
  for (const name of ["before", "after"])
    await page.route(`**/wardrobe-fixture/${name}.png`, (route) =>
      route.fulfill({
        path: path.join(evidence, `${name}.png`),
        contentType: "image/png",
      }),
    );
  await page.route("**/wardrobe-fixture/garment.png", (route) =>
    route.fulfill({
      path: path.resolve("../data/raw/catalog/edit-a59f077d.webp"),
      contentType: "image/webp",
    }),
  );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`/tryon?job=${job.jobId}`);
  const viewer = page.getByTestId("viewer");
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await expect(viewer.getByLabel("Result information")).toContainText(
    "Generated in 29.0 s",
  );
  for (const width of [1440, 375]) {
    await page.setViewportSize({ width, height: 900 });
    await viewer.getByRole("button", { name: "Inspect details" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("img", {
        name: "Actual garment reference used for this result",
      }),
    ).toBeVisible();
    await expect(dialog).toContainText("does not guarantee exact construction");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await dialog.screenshot({
      path: `../experiments/wardrobe-curation/inspection-${width}.png`,
    });
    await page.keyboard.press("Escape");
  }
  await viewer.getByRole("button", { name: "Slider", exact: true }).click();
  await viewer.getByRole("slider").fill("65");
  await expect(viewer.getByRole("slider")).toHaveValue("65");
  await viewer.screenshot({
    path: "../experiments/wardrobe-curation/result-mobile.png",
  });
  expect(errors).toEqual([]);
});
