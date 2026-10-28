import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { authenticatedSuite } from "./session-fixture";

authenticatedSuite(test);

// Transport fixtures deliberately use different bytes. They are not real
// product identities, approvals or successful model outputs.
const display = readFileSync(path.resolve("../data/raw/sage-polo.jpg"));
const reference = readFileSync(path.resolve("../data/raw/navy-tee.jpg"));
const product = {
  id: "transport-fixture",
  name: "Transport fixture shirt",
  category: "shirt",
  photoType: "model",
  imageUrl: "/api/v1/products/transport-fixture/image",
  referenceImageUrl: "/api/v1/products/transport-fixture/reference-image",
  description: "Transport test only",
  tryon_supported: true,
  brand_name: "Test fixture",
  audience: "men",
  colors: ["navy"],
  sizes: [],
  size_note: "Not inventory",
  license: "Test fixture only",
  source_url: "https://example.com/reference",
  displayImage: {
    license: "Display fixture only",
    attribution: "Test photographer",
    source_url: "https://example.com/display",
    photoType: "flat-lay",
  },
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/tryon/availability", (route) =>
    route.fulfill({
      json: { available: true, supportedCategories: ["shirt"] },
    }),
  );
  await page.route("**/api/v1/products?*", (route) =>
    route.fulfill({
      json: { items: [product], total: 1, offset: 0, limit: 12 },
    }),
  );
  await page.route("**/api/v1/products/transport-fixture", (route) =>
    route.fulfill({ json: product }),
  );
  await page.route("**/api/v1/products/transport-fixture/image", (route) =>
    route.fulfill({ contentType: "image/jpeg", body: display }),
  );
  await page.route(
    "**/api/v1/products/transport-fixture/reference-image",
    (route) => route.fulfill({ contentType: "image/jpeg", body: reference }),
  );
});

test("selected product sends reference bytes, category and ID; display stays on cards", async ({
  page,
}) => {
  let submitted: Buffer | null = null;
  await page.route("**/api/tryon", (route) => {
    submitted = route.request().postDataBuffer();
    return route.fulfill({
      status: 503,
      json: { detail: "Intentional transport-test outage" },
    });
  });
  await page.goto("/tryon?product=transport-fixture");
  const picker = page.locator(".garment-catalog");
  await expect(
    picker.getByText("Product photograph", { exact: true }),
  ).toBeVisible();
  await expect(
    picker.getByText("Model photograph", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByAltText("Selected garment conditioning image"),
  ).toBeVisible();
  await expect(page.getByLabel("Garment category")).toHaveValue("shirt");
  await page
    .getByLabel("Your person photo", { exact: true })
    .setInputFiles(path.resolve("../data/raw/studio-person.jpg"));
  const button = page.getByRole("button", {
    name: "Generate try-on",
    exact: true,
  });
  await expect(button).toBeEnabled();
  await button.click();
  await expect.poll(() => submitted !== null).toBe(true);
  const body = submitted as unknown as Buffer;
  expect(body.includes(reference)).toBe(true);
  expect(body.includes(display)).toBe(false);
  expect(body.toString()).toContain(
    'name="productId"\r\n\r\ntransport-fixture',
  );
  expect(body.toString()).toContain('name="garmentCategory"\r\n\r\nshirt');
  expect(body.toString()).toContain('name="garmentPhotoType"\r\n\r\nmodel');
});

test("missing inference reference never falls back to the display photograph", async ({
  page,
}) => {
  await page.route(
    "**/api/v1/products/transport-fixture/reference-image",
    (route) => route.fulfill({ status: 404 }),
  );
  await page.goto("/tryon?product=transport-fixture");
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByAltText("Selected garment conditioning image"),
  ).toHaveCount(0);
});

test("catalog cards and details show display image and distinct attribution on mobile", async ({
  page,
}) => {
  await page.route("**/api/v1/catalog/quality", (route) =>
    route.fulfill({
      json: { enforced: false, approvedCount: 0, targetCount: 20 },
    }),
  );
  await page.goto("/catalog");
  const cardImage = page.locator(".product-image img");
  await expect(cardImage).toHaveAttribute("src", product.imageUrl);
  await expect
    .poll(() => cardImage.evaluate((im: HTMLImageElement) => im.naturalWidth))
    .toBeGreaterThan(0);
  for (const width of [1440, 768, 375]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(
      await cardImage.evaluate((im) => getComputedStyle(im).objectFit),
    ).toBe("contain");
  }
  await page.getByRole("button", { name: `View ${product.name}` }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.locator("img").first()).toHaveAttribute(
    "src",
    product.imageUrl,
  );
  await expect(dialog).toContainText("Display fixture only");
  await expect(
    dialog.getByRole("link", {
      name: "Image source and attribution",
      exact: false,
    }),
  ).toHaveAttribute("href", product.displayImage.source_url);
  await dialog.getByText("View the garment reference used for try-on").click();
  await expect(dialog.locator("details img")).toHaveAttribute(
    "src",
    product.referenceImageUrl,
  );
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("favorites use the display image and recover after an image outage", async ({
  page,
}) => {
  await page.route("**/api/v1/favorites?*", (route) =>
    route.fulfill({
      json: { items: [product], total: 1, offset: 0, limit: 6 },
    }),
  );
  await page.route("**/api/v1/products/transport-fixture/image", (route) =>
    route.fulfill({ status: 404 }),
  );
  await page.goto("/profile");
  await page.getByRole("tab", { name: "Account settings" }).click();
  const card = page
    .locator(".private-history")
    .filter({ hasText: product.name });
  await expect(
    card.getByRole("img", { name: `${product.name}: image unavailable` }),
  ).toBeVisible();
  await expect(
    card.getByRole("link", { name: "Try this garment" }),
  ).toHaveAttribute("href", "/tryon?product=transport-fixture");
  await page.route("**/api/v1/products/transport-fixture/image", (route) =>
    route.fulfill({ contentType: "image/jpeg", body: display }),
  );
  await page.reload();
  await page.getByRole("tab", { name: "Account settings" }).click();
  await expect(card.locator("img")).toHaveAttribute("src", product.imageUrl);
  await expect
    .poll(() =>
      card.locator("img").evaluate((im: HTMLImageElement) => im.naturalWidth),
    )
    .toBeGreaterThan(0);
  expect(
    await card.locator("img").evaluate((im) => getComputedStyle(im).objectFit),
  ).toBe("contain");
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
