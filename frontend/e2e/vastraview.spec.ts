import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("VastraView branding, real catalog filters, product selection and mobile accessibility", async ({
  page,
}) => {
  const errors: string[] = [];
  page.setDefaultTimeout(15000);
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page).toHaveTitle(/VastraView/);
  await expect(page.getByRole("heading", { name: /Your Style/ })).toBeVisible();
  await expect(page.locator(".home-intro .brand-logo")).toBeVisible();
  await page
    .getByRole("link", { name: "Explore Collection", exact: true })
    .last()
    .click();
  await expect(page.locator(".product-card")).toHaveCount(12);
  await page.getByLabel("Search apparel").fill("navy");
  await expect(page.locator(".product-card")).toHaveCount(5);
  await page.getByLabel("Brand", { exact: true }).selectOption("nike");
  await expect(
    page.getByText("No published garments match these filters."),
  ).toBeVisible();
  await page.getByLabel("Brand", { exact: true }).selectOption("");
  await page.getByLabel("Search apparel").fill("sage");
  await page
    .getByRole("button", { name: "View Sage pique polo", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "commercial rights not established",
  );
  await page
    .getByRole("button", { name: "Try this garment", exact: true })
    .click();
  await expect(page).toHaveURL(/\/login\?returnTo=/);
  expect(new URL(page.url()).searchParams.get("returnTo")).toBe(
    "/tryon?product=sage-polo",
  );
  await page.goto("/catalog");
  await expect(page.locator(".product-card")).toHaveCount(12);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const heights = await page
      .locator(".product-image")
      .evaluateAll((images) =>
        images.map((image) => image.getBoundingClientRect().height),
      );
    expect(Math.max(...heights) - Math.min(...heights)).toBeLessThan(1);
    await page.screenshot({
      path: `../experiments/vastraview/catalog-${width}.png`,
      fullPage: true,
    });
  }
  const report = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(report.violations).toEqual([]);
  expect(errors).toEqual([]);
});

test("real account favorites, unit preference, private settings and deletion", async ({
  page,
}) => {
  const email = `vastra-${Date.now()}@example.com`,
    password = "Vastra!Browser2026";
  const registered = await page.request.post("/api/v1/auth/signup", {
    data: { name: "Vastra Browser", email, password, terms_accepted: true },
  });
  expect(registered.status()).toBe(201);
  try {
    await page.goto("/catalog");
    await page.getByLabel("Search apparel").fill("sage");
    await page
      .getByRole("button", { name: "View Sage pique polo", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Save favorite", exact: true })
      .click();
    await expect(page.getByText("Saved to your favorites.")).toBeVisible();
    await page.keyboard.press("Escape");
    await page.goto("/profile");
    await page.getByRole("tab", { name: "Account settings" }).click();
    await page.getByLabel("Preferred measurement units").selectOption("in");
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(page.getByText("Profile updated.")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Sage pique polo", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("This session", { exact: true })).toBeVisible();
    await page
      .getByRole("button", { name: "Delete account", exact: true })
      .click();
    await page.getByLabel("Confirm your password").fill(password);
    await page.getByRole("button", { name: "Delete permanently" }).click();
    await expect(
      page.getByRole("heading", { name: /Your Style/ }),
    ).toBeVisible();
    expect((await page.request.get("/api/v1/profile")).status()).toBe(401);
  } finally {
    await page.request.delete("/api/v1/profile", { data: { password } });
  }
});
