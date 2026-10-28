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
  const products = await (
    await page.request.get("/api/v1/products?limit=48")
  ).json();
  await expect(page.locator(".product-card")).toHaveCount(
    Math.min(12, products.total),
  );
  const navyCatalog = await (
    await page.request.get("/api/v1/products?q=navy")
  ).json();
  await page.getByLabel("Search apparel").fill("navy");
  await expect(page.locator(".product-card")).toHaveCount(
    Math.min(12, navyCatalog.total),
  );
  await page.getByLabel("Search apparel").fill("sage");
  await expect(page.locator(".product-card")).toHaveCount(0);
  expect((await page.request.get("/api/v1/products/sage-polo")).status()).toBe(
    404,
  );
  await page.goto("/tryon?product=sage-polo");
  await expect(page).toHaveURL(/\/login\?returnTo=/);
  expect(new URL(page.url()).searchParams.get("returnTo")).toBe(
    "/tryon?product=sage-polo",
  );
  await page.goto("/catalog");
  await expect(page.locator(".product-card")).toHaveCount(
    Math.min(12, products.total),
  );
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
    if (heights.length)
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
    const products = await (
      await page.request.get("/api/v1/products?limit=1")
    ).json();
    const chosen = products.items[0];
    if (chosen) {
      expect(
        (await page.request.put(`/api/v1/favorites/${chosen.id}`)).status(),
      ).toBe(204);
    } else {
      expect(
        (await page.request.put("/api/v1/favorites/sage-polo")).status(),
      ).toBe(404);
      expect(
        (await (await page.request.get("/api/v1/favorites")).json()).total,
      ).toBe(0);
    }
    await page.goto("/profile");
    await page.getByRole("tab", { name: "Account settings" }).click();
    await page.getByLabel("Preferred measurement units").selectOption("in");
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(page.getByText("Profile updated.")).toBeVisible();
    if (chosen)
      await expect(
        page.getByRole("heading", { name: chosen.name, exact: true }),
      ).toBeVisible();
    else
      await expect(
        page.getByRole("heading", { name: "Sage pique polo", exact: true }),
      ).toHaveCount(0);
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
