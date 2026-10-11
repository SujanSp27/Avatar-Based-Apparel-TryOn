import { test, expect } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

// Exact beige-shirt/striped-garment regression. The bundled demo has identical inputs.
const runFolder = path.resolve(
  "../data/processed/9658bcca-8a2b-4a88-a134-cea3ff8739dd",
);
const personPath = existsSync(path.join(runFolder, "personInput.bin"))
  ? path.join(runFolder, "personInput.bin")
  : path.resolve("../data/raw/studio-person.jpg");
const garmentPath = existsSync(path.join(runFolder, "garmentInput.bin"))
  ? path.join(runFolder, "garmentInput.bin")
  : path.resolve("../data/raw/garment-demo.png");

test("2D supports upper garments while 3D retains all categories", async ({
  page,
}) => {
  await page.goto("/");
  const mode = page.getByLabel("Try-on mode");
  const category = page.getByLabel("Garment category");
  await expect(mode).toHaveValue("2d");
  await expect(category.locator("option")).toHaveText(["T-shirt", "Shirt"]);
  await mode.selectOption("3d");
  await category.selectOption("dress");
  await mode.selectOption("2d");
  await expect(category).toHaveValue("t-shirt");
  await expect(page.getByLabel("Height in cm")).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "regular", exact: true }),
  ).toBeDisabled();
  await mode.selectOption("auto");
  await expect(category.locator("option")).toHaveText([
    "T-shirt",
    "Shirt",
    "Dress",
    "Trouser",
  ]);
  await expect(page.getByLabel("Height in cm")).toBeEnabled();
});

test("missing pretrained model returns a clear error without an overlay result", async ({
  page,
  request,
}) => {
  const healthResponse = await request.get("/api/health");
  expect(healthResponse.ok()).toBe(true);
  const health = await healthResponse.json();
  expect(typeof health.vton2d?.available).toBe("boolean");
  test.skip(
    health.vton2d.available,
    "The pretrained model is configured; this test covers its unavailable state.",
  );
  expect(health.vton2d.reason).toEqual(expect.any(String));
  await page.goto("/");
  await expect(page.getByLabel("Try-on mode")).toHaveValue("2d");
  await page.getByRole("button", { name: "Try sample photos" }).click();
  await expect(page.getByAltText("person upload preview")).toBeVisible();
  await expect(page.getByTestId("model-status")).toContainText(
    health.vton2d.reason,
  );
  await expect(
    page.getByRole("button", { name: "Generate try-on" }),
  ).toBeDisabled();
  // The UI avoids a known failing request; direct API callers still receive a typed error.
  const response = await request.post("/api/tryon", {
    multipart: {
      personImage: {
        name: "studio-person.jpg",
        mimeType: "image/jpeg",
        buffer: readFileSync(personPath),
      },
      garmentImage: {
        name: "garment.png",
        mimeType: "image/png",
        buffer: readFileSync(garmentPath),
      },
      brandId: "1",
      garmentCategory: "t-shirt",
      fitPreference: "regular",
      tryonMode: "2d",
    },
    timeout: 120000,
  });
  expect(response.status()).toBe(503);
  const failure = await response.json();
  expect([
    "vton_model_unavailable",
    "vton_device_unavailable",
    "vton_dependency_unavailable",
  ]).toContain(failure.error.code);
  expect(failure.error.message.length).toBeGreaterThan(20);
  await expect(page.getByTestId("photo-result")).toHaveCount(0);
  await expect(page.getByTestId("recommended-size")).toHaveCount(0);
  await expect(page.getByTestId("viewer")).toHaveAttribute(
    "data-loaded",
    "false",
  );
  await expect(
    page.getByRole("link", { name: "Download try-on PNG" }),
  ).toHaveCount(0);
  await page.getByLabel("Try-on mode").selectOption("3d");
  await expect(
    page.getByRole("button", { name: "Generate try-on" }),
  ).toBeEnabled();
  await expect(page.getByTestId("model-status")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("striped-garment regression produces a pretrained 2D result", async ({
  page,
  request,
}) => {
  test.setTimeout(600000);
  test.skip(
    !existsSync(personPath) || !existsSync(garmentPath),
    "Regression inputs and their bundled equivalents are absent in this checkout.",
  );
  const healthResponse = await request.get("/api/health");
  expect(healthResponse.ok()).toBe(true);
  const health = await healthResponse.json();
  expect(typeof health.vton2d?.available).toBe("boolean");
  test.skip(
    !health.vton2d.available,
    `Pretrained inference is unavailable: ${health.vton2d.reason}. No result quality claim is made.`,
  );
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  await page.goto("/");
  await expect(page.getByLabel("Try-on mode")).toHaveValue("2d");
  await page.getByLabel("Upload person image").setInputFiles({
    name: "studio-person.jpg",
    mimeType: "image/jpeg",
    buffer: readFileSync(personPath),
  });
  await page.getByLabel("Upload garment image").setInputFiles({
    name: "garment.png",
    mimeType: "image/png",
    buffer: readFileSync(garmentPath),
  });
  await page.getByLabel("Brand", { exact: true }).selectOption("1");
  await page.getByLabel("Garment category").selectOption("t-shirt");
  const pending = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/tryon") &&
      response.request().method() === "POST",
    { timeout: 550000 },
  );
  await page.getByRole("button", { name: "Generate try-on" }).click();
  const response = await pending;
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.mode).toBe("2d");
  expect(result.renderingMethod).toBe("pretrained-vton");
  expect(result.provenance.backend).not.toMatch(/overlay|template|warp/i);
  expect(result.measurements).toBeNull();
  expect(result.recommendedSize).toBeNull();
  expect(result.avatarUrl).toBeNull();
  expect(result.bodyUrl).toBeNull();
  expect(result.garmentUrl).toBeNull();
  expect(result.warnings.length).toBeGreaterThan(0);
  await expect(
    page.getByRole("heading", { name: "2D virtual try-on", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("recommended-size")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  const viewer = page.getByTestId("viewer");
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await expect(viewer.locator("img")).toBeVisible();

  for (const url of [result.previewUrl, result.originalUrl]) {
    expect(typeof url).toBe("string");
    const image = await request.get(new URL(url, response.url()).href);
    expect(image.status()).toBe(200);
    expect(image.headers()["content-type"]).toContain("image/png");
    expect((await image.body()).subarray(0, 8).toString("hex")).toBe(
      "89504e470d0a1a0a",
    );
  }

  await page.getByRole("button", { name: "Original", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Original", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  const originalSource = await viewer.locator("img").getAttribute("src");
  await page.getByRole("button", { name: "Try-on", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Try-on", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  expect(await viewer.locator("img").getAttribute("src")).not.toBe(
    originalSource,
  );
  expect(
    await viewer
      .locator("img")
      .evaluate(
        (image: HTMLImageElement) =>
          image.complete && image.naturalWidth > 0 && image.naturalHeight > 0,
      ),
  ).toBe(true);
  expect(browserErrors).toEqual([]);
  await page.screenshot({
    path: "../experiments/runs/browser-pretrained-2d.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../experiments/runs/browser-pretrained-2d-mobile.png",
    fullPage: true,
  });
});
