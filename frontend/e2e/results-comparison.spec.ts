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
  after: "ok" | "error" | "mismatch" | "pending" | "resized" = "ok",
  images = evidence,
) {
  await page.route("**/api/tryon/availability", (route) =>
    route.fulfill({ json: { available: true, reason: null } }),
  );
  await page.route("**/comparison-test/before.png*", (route) =>
    route.fulfill({
      path: path.join(images, "original.png"),
      contentType: "image/png",
    }),
  );
  await page.route("**/comparison-test/after.png*", async (route) => {
    if (after === "error") return route.fulfill({ status: 404 });
    if (after === "pending") return; // Deliberately stalled download; timeout is tested with browser clock.
    if (after === "resized") {
      // Same retained neural photograph at half resolution; no generated mock outfit.
      const image = readFileSync(path.join(images, "after.png")).toString(
        "base64",
      );
      return route.fulfill({
        contentType: "image/svg+xml",
        body: `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600" viewBox="0 0 800 1200"><image width="800" height="1200" href="data:image/png;base64,${image}"/></svg>`,
      });
    }
    return route.fulfill({
      path:
        after === "mismatch"
          ? path.resolve("../data/raw/navy-tee.jpg")
          : path.join(images, "after.png"),
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
  for (const width of [3840, 1920, 1440, 768, 375]) {
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
    await expectAlignedImages(page);
    const frame = await viewer.locator(".compare-stage").boundingBox();
    const card = (await viewer.boundingBox())!;
    const layout = (await page.locator(".tryon-result").boundingBox())!;
    expect(card.width).toBeLessThanOrEqual(1100);
    expect(frame!.height).toBeLessThanOrEqual(width > 900 ? 540 : 500);
    if (width >= 1440) expect(frame!.height).toBeCloseTo(540, 0);
    expect(
      Math.abs(card.x + card.width / 2 - (layout.x + layout.width / 2)),
    ).toBeLessThan(1);
    const heading = (await viewer.locator(".comparison-header").boundingBox())!;
    expect(heading.y + heading.height).toBeLessThanOrEqual(frame!.y);
    const footer = (await viewer.locator(".comparison-footer").boundingBox())!;
    expect(footer.y).toBeGreaterThanOrEqual(frame!.y + frame!.height);
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
  expect(bounds.height).toBeCloseTo(540, 0);
  const splitCard = (await viewer.locator(".comparison-frame").boundingBox())!;
  // Slider mode also shrinks to its photograph; no wide empty side gutters.
  expect(splitCard.width - bounds.width).toBeCloseTo(26, 0);
  const inspect = (await viewer
    .getByRole("button", { name: "Inspect details" })
    .boundingBox())!;
  const download = (await viewer
    .getByRole("link", { name: "Download render" })
    .boundingBox())!;
  expect(inspect.y).toBe(download.y);
  expect(download.x).toBeGreaterThan(inspect.x + inspect.width);
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

async function expectAlignedImages(page: Page) {
  const geometry = await page.locator(".compare-stage").evaluate((stage) => {
    const frame = stage.getBoundingClientRect();
    const images = [...stage.querySelectorAll("img")].map((image) => {
      const box = image.getBoundingClientRect();
      // Compare the painted photograph, not just its potentially letterboxed element.
      const scale = Math.min(
        box.width / image.naturalWidth,
        box.height / image.naturalHeight,
      );
      return {
        left: box.left + (box.width - image.naturalWidth * scale) / 2,
        right: box.right - (box.width - image.naturalWidth * scale) / 2,
        top: box.top + (box.height - image.naturalHeight * scale) / 2,
        width: image.naturalWidth * scale,
        height: image.naturalHeight * scale,
      };
    });
    return {
      images,
      frame: { left: frame.left, width: frame.width, height: frame.height },
    };
  });
  const [before, after] = geometry.images;
  expect(Math.abs(before.width - after.width)).toBeLessThan(0.05);
  expect(Math.abs(before.height - after.height)).toBeLessThan(0.05);
  expect(Math.abs(before.top - after.top)).toBeLessThan(0.05);
  expect(Math.abs(before.height - geometry.frame.height)).toBeLessThan(0.05);
  expect(Math.abs(before.left - geometry.frame.left)).toBeLessThan(0.05);
  expect(Math.abs(before.right - after.left)).toBeLessThan(0.05);
  expect(
    Math.abs(before.width + after.width - geometry.frame.width),
  ).toBeLessThan(0.05);
}

for (const person of ["male", "female"]) {
  test(`${person} full-body turquoise shorts have no center gap or unequal scaling`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const viewer = await fixture(
      page,
      "ok",
      path.resolve(`../experiments/comparison-alignment/${person}-shorts`),
    );
    await expect(viewer).toHaveAttribute("data-loaded", "true");
    for (const width of [1920, 1440, 768, 375]) {
      await page.setViewportSize({ width, height: 1050 });
      await expectAlignedImages(page);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      if (width === 1440 || width === 375)
        await viewer.screenshot({
          path: `../experiments/compact-comparison/${person}-shorts-${width}.png`,
        });
    }
    await viewer.getByRole("button", { name: "Slider", exact: true }).click();
    const slider = viewer.getByRole("slider", {
      name: "Before and after comparison slider",
    });
    for (const value of [0, 25, 50, 75, 100]) {
      await slider.fill(String(value));
      const divider = await viewer.locator(".compare-divider").boundingBox();
      const frame = (await viewer.locator(".compare-stage").boundingBox())!;
      expect(
        Math.abs(
          divider!.x +
            divider!.width / 2 -
            (frame.x + (frame.width * value) / 100),
        ),
      ).toBeLessThan(0.1);
      const originals = await viewer
        .locator(".compare-original img")
        .boundingBox();
      const generated = await viewer
        .locator(".compare-result img")
        .boundingBox();
      expect(generated).toEqual(originals);
    }
    await viewer.screenshot({
      path: `../experiments/compact-comparison/${person}-shorts-slider.png`,
    });
    expect(errors).toEqual([]);
  });
}

test("a lower-resolution render with matching framing aligns without cropping", async ({
  page,
}) => {
  const viewer = await fixture(page, "resized");
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await expectAlignedImages(page);
  await expect(
    viewer.getByRole("link", { name: "Download render" }),
  ).toBeVisible();
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
    .getByRole("button", { name: "Change outfit", exact: true })
    .click();
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

test("completed comparison is compact and centered; editing keeps the selected render", async ({
  page,
}) => {
  const viewer = await fixture(page);
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await expect(page.locator("#tryon-inputs")).toBeHidden();
  const layout = (await page.locator(".tryon-layout").boundingBox())!;
  const comparison = (await viewer.boundingBox())!;
  expect(comparison.width).toBeLessThan(layout.width);
  expect(comparison.width).toBeLessThanOrEqual(1100);
  expect(
    Math.abs(
      layout.x + layout.width / 2 - (comparison.x + comparison.width / 2),
    ),
  ).toBeLessThan(1);
  await viewer.getByRole("button", { name: "Slider", exact: true }).click();
  await page
    .getByRole("button", { name: "Change outfit", exact: true })
    .click();
  await expect(page.locator("#tryon-inputs")).toBeVisible();
  await expect(viewer.locator(".compare-stage")).toHaveClass(/split/);
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveAttribute("src", result.previewUrl);
  await page
    .getByRole("button", { name: "Focus on result", exact: true })
    .click();
  await expect(page.locator("#tryon-inputs")).toBeHidden();
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  // A restored result has no File input in memory. Choosing another garment
  // must restore this result's original person instead of using a demo person.
  await page.getByRole("button", { name: /Sage pique polo/ }).click();
  await expect(page.locator("#tryon-inputs")).toBeVisible();
  await expect(
    page.getByText("original-person.png", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Garment photo type", { exact: true }),
  ).toHaveValue("flat-lay");
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeEnabled();
  const selectedPhoto = viewer.getByRole("img", {
    name: "Your selected person photo",
  });
  await expect(selectedPhoto).toHaveAttribute("src", /^blob:/);
  const actualHash = await selectedPhoto.evaluate(async (image) => {
    const bytes = await (
      await fetch((image as HTMLImageElement).src)
    ).arrayBuffer();
    const hash = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(hash), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
  });
  expect(actualHash).toBe(
    createHash("sha256")
      .update(readFileSync(path.join(evidence, "original.png")))
      .digest("hex"),
  );
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveCount(0);
});

test("a newer selection in another tab replaces the old render using GET only", async ({
  page,
  context,
}) => {
  let posts = 0;
  context.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/tryon"))
      posts++;
  });
  const viewer = await fixture(page);
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  const nextId = "00000000-0000-4000-8000-000000000066";
  const second = await context.newPage();
  await second.goto("/terms");
  await page.route("**/comparison-test/new-tab-result.png", (route) =>
    route.fulfill({
      path: path.join(evidence, "after.png"),
      contentType: "image/png",
    }),
  );
  await page.route(`**/api/tryon/jobs/${nextId}`, (route) =>
    route.fulfill({
      json: {
        jobId: nextId,
        status: "success",
        result: {
          ...result,
          previewUrl: "/comparison-test/new-tab-result.png",
        },
      },
    }),
  );
  await second.evaluate(
    (id) => localStorage.setItem("form-fit-last-job", id),
    nextId,
  );
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveAttribute("src", "/comparison-test/new-tab-result.png");
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  // Rapid older events must not resurrect an intermediate job or stop polling.
  await second.evaluate((id) => {
    localStorage.setItem(
      "form-fit-last-job",
      "00000000-0000-4000-8000-000000000055",
    );
    localStorage.setItem("form-fit-last-job", id);
  }, nextId);
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await second.evaluate(() => localStorage.removeItem("form-fit-last-job"));
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator("#tryon-inputs")).toBeVisible();
  expect(posts).toBe(0);
  await second.close();
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
      "Private image link copied. It requires your session; use Download render to share the image with someone else.",
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
