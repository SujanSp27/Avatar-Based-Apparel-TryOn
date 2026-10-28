import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { authenticatedSuite } from "./session-fixture";

authenticatedSuite(test);

test("published wardrobe excludes rejected routes and shows an honest shortfall", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const quality = await (
    await page.request.get("/api/v1/catalog/quality")
  ).json();
  expect(quality.enforced).toBe(true);
  expect(quality.approvedCount).toBeLessThanOrEqual(20);
  const products = await (
    await page.request.get("/api/v1/products?limit=48")
  ).json();
  expect(products.total).toBe(quality.approvedCount);
  for (const product of products.items)
    expect(product.qualityReview.status).toBe("approved");
  for (const route of [
    "/api/v1/products/sage-polo",
    "/api/v1/products/sage-polo/image",
    "/api/garments/sage-polo/image",
  ])
    expect((await page.request.get(route)).status()).toBe(404);
  expect((await page.request.put("/api/v1/favorites/sage-polo")).status()).toBe(
    404,
  );
  await page.goto("/catalog");
  await expect(page.locator(".product-card")).toHaveCount(
    Math.min(12, products.total),
  );
  if (quality.approvedCount < 20)
    await expect(
      page.getByText(`${quality.approvedCount} of 20 garments approved`),
    ).toBeVisible();
  if (quality.approvedCount === 0) {
    await expect(
      page.getByText(
        "No garments have passed the complete quality review yet.",
      ),
    ).toBeVisible();
    await expect(
      page.getByLabel("Garment type", { exact: true }).locator("option"),
    ).toHaveCount(1);
    await page.getByRole("searchbox").fill("sage");
    await expect(page.getByText("Opening the collection…")).toHaveCount(0);
    await expect(page.locator(".product-card")).toHaveCount(0);
  }
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 950 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `../experiments/wardrobe-review/curated-catalog-${width}.png`,
      fullPage: true,
    });
  }
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.goto("/tryon?product=sage-polo");
  await expect(
    page.getByText("Product is unavailable.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByAltText("Selected garment conditioning image"),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeDisabled();
  if (quality.approvedCount === 0) {
    await expect(
      page.getByText("No approved garments in this collection yet.", {
        exact: false,
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Try sample photos" }).click();
    await expect(
      page.getByText("The sample person is ready.", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByAltText("Selected garment conditioning image"),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Generate try-on", exact: true }),
    ).toBeDisabled();
  }
  expect(errors).toEqual([]);
});
