import { test, expect } from "@playwright/test";
import path from "node:path";

test("real uploads produce measurements, size and interactive GLB", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("Try-on mode").selectOption("3d");
  await expect(
    page.getByRole("heading", { name: "A new perspective on fit." }),
  ).toBeVisible();
  await page
    .getByLabel("Upload person image")
    .setInputFiles(path.resolve("../data/raw/studio-person.jpg"));
  await page
    .getByLabel("Upload garment image")
    .setInputFiles(path.resolve("../data/raw/garment-demo.png"));
  await page.getByLabel("Brand", { exact: true }).selectOption("1");
  await page.getByLabel("Garment category").selectOption("t-shirt");
  await page.getByLabel("Height in cm").fill("172");
  await page.getByRole("button", { name: "regular", exact: true }).click();
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/api/tryon") && r.request().method() === "POST",
    { timeout: 180000 },
  );
  await page.getByRole("button", { name: "Generate try-on" }).click();
  expect((await response).status()).toBe(200);
  await expect(page.getByTestId("recommended-size")).toBeVisible();
  await expect(page.getByTestId("viewer")).toHaveAttribute(
    "data-loaded",
    "true",
    { timeout: 60000 },
  );
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByRole("button", { name: "side", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "side", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({
    path: "../experiments/browser-side.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "back", exact: true }).click();
  await page.getByRole("button", { name: "Rotate 360 degrees" }).click();
  await expect(
    page.getByRole("button", { name: "Rotate 360 degrees" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "front", exact: true }).click();
  const canvas = page.locator("canvas");
  const bounds = await canvas.boundingBox();
  expect(bounds).not.toBeNull();
  await page.mouse.move(
    bounds!.x + bounds!.width / 2,
    bounds!.y + bounds!.height / 2,
  );
  await page.mouse.wheel(0, -180);
  await page.getByRole("button", { name: "body", exact: true }).click();
  await expect(page.getByTestId("viewer")).toHaveAttribute(
    "data-loaded",
    "true",
  );
  await page.getByRole("button", { name: "garment", exact: true }).click();
  await expect(page.getByTestId("viewer")).toHaveAttribute(
    "data-loaded",
    "true",
  );
  await page.getByRole("button", { name: "dressed", exact: true }).click();
  await expect(page.getByTestId("viewer")).toHaveAttribute(
    "data-loaded",
    "true",
  );
  await page.getByRole("button", { name: "front", exact: true }).click();
  await page.screenshot({
    path: "../experiments/browser-complete.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("sample button and mobile input layout work", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Try sample photos" }).click();
  await expect(page.getByAltText("person upload preview")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate try-on" }),
  ).toBeEnabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../experiments/browser-mobile.png",
    fullPage: true,
  });
});
