import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { signInForTest } from "./session-fixture";

test("editorial hero and catalog images load across desktop and mobile", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto("/");
  const photo = page.locator(".editorial-photo img");
  await expect(photo).toBeVisible();
  await expect.poll(() => photo.evaluate((im: HTMLImageElement) => im.naturalWidth)).toBeGreaterThan(0);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `../experiments/vastraview/hero-${width}.png`, fullPage: true });
  }
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  const catalog = await (await page.request.get("/api/v1/products?limit=48")).json();
  const rest = await (await page.request.get("/api/v1/products?limit=48&offset=48")).json();
  const products = [...catalog.items, ...rest.items];
  expect(products).toHaveLength(57);
  for (const item of products) {
    const image = await page.request.get(item.imageUrl);
    expect(image.status()).toBe(200);
    expect(image.headers()["content-type"]).toMatch(/^image\//);
    expect((await image.body()).length).toBeGreaterThan(1000);
  }
  await page.goto("/catalog");
  await page.getByLabel("Garment type", { exact: true }).selectOption("saree");
  await expect(page.locator(".product-card")).toHaveCount(1);
  await page.getByRole("button", { name: "View Charcoal patterned saree" }).click();
  await expect(page.getByRole("button", { name: "Try this garment" })).toBeDisabled();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByLabel("Color", { exact: true }).selectOption("blue");
  await expect.poll(() => page.locator(".product-card").count()).toBeGreaterThan(1);
  await page.route("**/api/v1/products/*/image", route => route.fulfill({ status: 404 }));
  await page.getByLabel("Color", { exact: true }).selectOption("burgundy");
  await expect(page.getByText("Photograph temporarily unavailable").first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("chart country, source, subset measurements and unit switching stay correct", async ({ page }) => {
  await page.goto("/sizing");
  await page.getByLabel("Brand", { exact: true }).selectOption("adidas");
  await page.getByLabel("Country / region").selectOption("IN");
  await expect(page.getByText("No verified body chart", { exact: false })).toBeVisible();
  await page.getByLabel("Country / region").selectOption("GB");
  await expect(page.locator(".chart-provenance")).toContainText("United Kingdom");
  await expect(page.getByLabel("Shoulder width", { exact: true })).toHaveCount(0);
  for (const [label, value] of [["Chest circumference", "96.5"], ["Waist circumference", "84.5"], ["Hip circumference", "95.5"]]) {
    await page.getByLabel(label, { exact: true }).fill(value);
  }
  await page.getByRole("button", { name: "Find my size", exact: true }).click();
  await expect(page.getByTestId("recommended-size")).toHaveText("M");
  await page.getByLabel("Measurement units").selectOption("in");
  expect(Number(await page.getByLabel("Chest circumference", { exact: true }).inputValue())).toBeCloseTo(96.5 / 2.54, 2);
  await expect(page.getByTestId("recommended-size")).toHaveText("M");
  await page.getByLabel("Measurement units").selectOption("cm");
  await expect(page.getByLabel("Chest circumference", { exact: true })).toHaveValue("96.5");
  await page.getByRole("button", { name: "Explore the size chart", exact: false }).click();
  await expect(page.getByRole("dialog")).toContainText("Source verified");
  await page.getByLabel("Display units").selectOption("in");
  await expect(page.getByRole("dialog").getByRole("table")).toContainText("36.6");
  await page.keyboard.press("Escape");
  await page.getByLabel("Brand", { exact: true }).selectOption("manyavar");
  await page.getByLabel("Country / region").selectOption("IN");
  await page.getByLabel("Category", { exact: true }).selectOption("kurta");
  await expect(page.locator(".chart-provenance")).toContainText("India");
  await expect(page.getByLabel("Shoulder width", { exact: true })).toBeVisible();
});

test("guest return URL survives sign-in and logout blocks new uploads", async ({ page }) => {
  await page.goto("/tryon?product=sage-polo");
  await expect(page).toHaveURL(/\/login\?returnTo=/);
  const password = await signInForTest(page);
  try {
    // Actual cookie session, real backend image download; no inference is submitted.
    await page.goto("/tryon?product=sage-polo");
    await expect(page.getByAltText("Selected garment conditioning image")).toBeVisible();
    await expect(page.getByLabel("Garment category", { exact: true })).toHaveValue("t-shirt");
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await page.goto("/tryon");
    await expect(page).toHaveURL(/\/login\?returnTo=/);
    const response = await page.request.post("/api/tryon", { multipart: {
      personImage: { name: "p.png", mimeType: "image/png", buffer: Buffer.from("bad") },
      garmentImage: { name: "g.png", mimeType: "image/png", buffer: Buffer.from("bad") },
      garmentCategory: "t-shirt",
    } });
    expect(response.status()).toBe(401);
  } finally {
    // Logged-out test account has no saved images or private history.
    void password;
  }
});
