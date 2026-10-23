import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import AxeBuilder from "@axe-core/playwright";

// These are transport/layout tests against a retained real neural render.
// They do not establish model quality or send another inference request.
const evidence = path.resolve("../experiments/results-redesign/navy-tee");
const saved = JSON.parse(
  readFileSync(path.join(evidence, "live-result.json"), "utf8"),
);
const jobId = "00000000-0000-4000-8000-000000000055";
const result = {
  ...saved.result,
  originalUrl: "/comparison-test/before.png",
  previewUrl: "/comparison-test/after.png",
};

async function fixture(
  page: Page,
  after: "ok" | "error" | "mismatch" | "pending" = "ok",
) {
  await page.route("**/api/tryon/availability", (route) =>
    route.fulfill({ json: { available: true, reason: null } }),
  );
  await page.route("**/comparison-test/before.png*", (route) =>
    route.fulfill({
      path: path.join(evidence, "original.png"),
      contentType: "image/png",
    }),
  );
  await page.route("**/comparison-test/after.png*", async (route) => {
    if (after === "error") return route.fulfill({ status: 404 });
    if (after === "pending") return; // Deliberately stalled download; timeout is tested with browser clock.
    return route.fulfill({
      path:
        after === "mismatch"
          ? path.resolve("../data/raw/navy-tee.jpg")
          : path.join(evidence, "after.png"),
      contentType: after === "mismatch" ? "image/jpeg" : "image/png",
    });
  });
  await page.route("**/api/tryon/jobs/*", (route) =>
    route.fulfill({ json: { jobId, status: "success", result } }),
  );
  await page.goto(`/tryon?job=${jobId}`);
  return page.getByTestId("viewer");
}

test("equal panels fill the frame on desktop, tablet and mobile; pointer and keyboard slider work", async ({
  page,
}) => {
  const viewer = await fixture(page);
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  for (const width of [1440, 768, 375]) {
    await page.setViewportSize({ width, height: 1000 });
    const boxes = await viewer
      .locator(".compare-original, .compare-result")
      .evaluateAll((els) =>
        els.map((el) => {
          const r = el.getBoundingClientRect();
          return { width: r.width, height: r.height, top: r.top };
        }),
      );
    expect(Math.abs(boxes[0].width - boxes[1].width)).toBeLessThan(1);
    expect(boxes[0].height).toBe(boxes[1].height);
    expect(boxes[0].top).toBe(boxes[1].top);
    const frame = await viewer.locator(".compare-stage").boundingBox();
    expect(
      Math.abs(boxes[0].width + boxes[1].width - frame!.width),
    ).toBeLessThan(3);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.setViewportSize({ width: 1440, height: 1050 });
  await viewer.getByRole("button", { name: "Slider", exact: true }).click();
  const slider = viewer.getByRole("slider", {
    name: "Before and after comparison slider",
  });
  await slider.scrollIntoViewIfNeeded();
  const bounds = (await slider.boundingBox())!;
  await page.mouse.move(bounds.x + bounds.width * 0.5, bounds.y + 120);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width * 0.75, bounds.y + 120, {
    steps: 10,
  });
  await page.mouse.up();
  expect(Number(await slider.inputValue())).toBeCloseTo(75, 0);
  await slider.focus();
  await page.keyboard.press("Home");
  await expect(slider).toHaveValue("0");
  await page.keyboard.press("End");
  await expect(slider).toHaveValue("100");
  await viewer
    .getByRole("button", { name: "Side by side", exact: true })
    .click();
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    scan.violations.map((v) => ({
      id: v.id,
      targets: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
});

test("failed image cannot be downloaded or shared, and retry loads the saved result", async ({
  page,
}) => {
  const viewer = await fixture(page, "error");
  await expect(viewer.getByRole("alert")).toContainText("could not load");
  await expect(
    viewer.getByRole("button", { name: "Download render" }),
  ).toBeDisabled();
  await expect(
    viewer.getByRole("button", { name: "Share", exact: true }),
  ).toBeDisabled();
  await page.route("**/comparison-test/after.png*", (route) =>
    route.fulfill({
      path: path.join(evidence, "after.png"),
      contentType: "image/png",
    }),
  );
  await viewer.getByRole("button", { name: "Retry images" }).click();
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  const event = page.waitForEvent("download");
  await viewer.getByRole("link", { name: "Download render" }).click();
  const download = await event;
  expect(download.suggestedFilename()).toBe("formfit-tryon.png");
  const hash = (bytes: Buffer) =>
    createHash("sha256").update(bytes).digest("hex");
  expect(hash(readFileSync((await download.path())!))).toBe(
    hash(readFileSync(path.join(evidence, "after.png"))),
  );
});

test("a stalled image offers retry after the bounded loading period", async ({
  page,
}) => {
  await page.clock.install();
  const viewer = await fixture(page, "pending");
  await expect(viewer.getByRole("status")).toContainText(
    "Loading your comparison",
  );
  await page.clock.fastForward(16000);
  await expect(
    viewer.getByRole("button", { name: "Retry images" }),
  ).toBeVisible();
  await expect(viewer).toHaveAttribute("aria-busy", "false");
});

test("dimension mismatch is reported instead of stretching the person", async ({
  page,
}) => {
  const viewer = await fixture(page, "mismatch");
  await expect(viewer.getByRole("alert")).toContainText("cannot be aligned");
  await expect(
    viewer.getByRole("link", { name: "Download render" }),
  ).toHaveCount(0);
});

test("changing a garment invalidates the saved result; a new job retains mode and uses the new image", async ({
  page,
}) => {
  const viewer = await fixture(page);
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await viewer.getByRole("button", { name: "Slider", exact: true }).click();
  await page.getByRole("button", { name: "Try sample photos" }).click();
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeEnabled();
  expect(
    await page.evaluate(() => localStorage.getItem("form-fit-last-job")),
  ).toBeNull();
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveCount(0);
  await page.getByLabel("Filter garment catalog").selectOption("dress");
  await page.getByRole("button", { name: /Coral ruched dress/ }).click();
  await expect(
    page.getByLabel("Garment category", { exact: true }),
  ).toHaveValue("dress");
  await expect(
    page.getByLabel("Garment photo type", { exact: true }),
  ).toHaveValue("model");
  let complete = false;
  let posted = "";
  await page.route("**/api/tryon", async (route) => {
    posted = route.request().headers()["idempotency-key"];
    expect(route.request().postData()).toContain(
      'name="garmentCategory"\r\n\r\ndress',
    );
    await route.fulfill({ status: 202, json: { jobId: posted } });
  });
  await page.route("**/comparison-test/new-result.png", (route) =>
    route.fulfill({
      path: path.join(evidence, "after.png"),
      contentType: "image/png",
    }),
  );
  await page.route("**/api/tryon/jobs/*", (route) =>
    route.fulfill({
      json: complete
        ? {
            status: "success",
            jobId: posted,
            result: {
              ...result,
              previewUrl: "/comparison-test/new-result.png",
              runId: "new-transport-test-result",
            },
          }
        : {
            status: "processing",
            jobId: posted,
            progress: { stage: "generating" },
          },
    }),
  );
  await page
    .getByRole("button", { name: "Generate try-on", exact: true })
    .click();
  await expect(viewer).toContainText("Creating your next look");
  await expect(
    viewer.getByRole("link", { name: "Download render" }),
  ).toHaveCount(0);
  complete = true;
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await expect(viewer.locator(".compare-stage")).toHaveClass(/split/);
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveAttribute("src", "/comparison-test/new-result.png");
  await page
    .getByLabel("Garment category", { exact: true })
    .selectOption("shirt");
  await page.reload();
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(() => localStorage.getItem("form-fit-last-job")),
  ).toBeNull();
});

test("share uses the displayed final image, with a clear local-link fallback", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "canShare", {
      value: () => false,
      configurable: true,
    });
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: async (text: string) => {
          sessionStorage.setItem("shared-image-url", text);
        },
      },
      configurable: true,
    });
  });
  const viewer = await fixture(page);
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await viewer.getByRole("button", { name: "Share", exact: true }).click();
  await expect(
    page.getByText(
      "Image link copied. This local link works where your studio is accessible.",
    ),
  ).toBeVisible();
  expect(
    await page.evaluate(() => sessionStorage.getItem("shared-image-url")),
  ).toBe("http://127.0.0.1:5173/comparison-test/after.png");
  await viewer.getByRole("button", { name: "Inspect details" }).click();
  await expect(page.getByRole("dialog")).toContainText("800 × 1200 pixels");
  await expect(
    page
      .getByRole("dialog")
      .getByRole("link", { name: /View my size recommendations/ }),
  ).toHaveAttribute("href", "/sizing");
});
