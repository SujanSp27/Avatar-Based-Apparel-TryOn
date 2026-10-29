import { test, expect, request as newRequest } from "@playwright/test";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { randomUUID, createHash } from "node:crypto";
import path from "node:path";

// Opt-in, real private Colab inference. Persist the same idempotency key, browser
// session, and job ID so an interrupted test can resume without another render.
const root = path.resolve("..");
const caseName = process.env.VASTRAVIEW_LIVE_CASE ?? "";
if (caseName && !/^[a-z0-9-]{1,40}$/.test(caseName))
  throw new Error("Invalid live verification case");
const suffix = caseName ? `-${caseName}` : "";
const stateFile = path.join(root, `.runtime/vastraview-live${suffix}-job.json`);
const sessionFile = path.join(
  root,
  `.runtime/vastraview-live${suffix}-session.json`,
);
const evidence = path.join(
  root,
  `experiments/vastraview/private-tryon${suffix}`,
);
type State = {
  idempotencyKey: string;
  jobId?: string;
  inputFingerprint?: string;
};

test("real private Colab result survives refresh, denies strangers and downloads correctly", async ({
  page,
  context,
}) => {
  test.skip(
    process.env.VASTRAVIEW_LIVE !== "1",
    "Explicit opt-in required for one private Colab inference.",
  );
  test.setTimeout(300000);
  mkdirSync(evidence, { recursive: true });
  const personPath = path.resolve(
    root,
    process.env.VASTRAVIEW_LIVE_PERSON ?? "data/raw/studio-person.jpg",
  );
  const garmentPath = path.resolve(
    root,
    process.env.VASTRAVIEW_LIVE_GARMENT ?? "data/raw/sage-polo.jpg",
  );
  const category = process.env.VASTRAVIEW_LIVE_CATEGORY ?? "t-shirt";
  const photoType = process.env.VASTRAVIEW_LIVE_PHOTO_TYPE ?? "flat-lay";
  const upload = (filename: string) => {
    const mimeTypes: Record<string, string> = {
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".png": "image/png",
      ".webp": "image/webp",
    };
    const mimeType = mimeTypes[path.extname(filename).toLowerCase()];
    if (!mimeType)
      throw new Error("Live-test images must be JPEG, PNG or WebP");
    return {
      name: path.basename(filename),
      mimeType,
      buffer: readFileSync(filename),
    };
  };
  const person = upload(personPath),
    garment = upload(garmentPath);
  const inputFingerprint = createHash("sha256")
    .update(JSON.stringify({ category, photoType }))
    .update(createHash("sha256").update(person.buffer).digest())
    .update(createHash("sha256").update(garment.buffer).digest())
    .digest("hex");
  const state: State = existsSync(stateFile)
    ? JSON.parse(readFileSync(stateFile, "utf8"))
    : { idempotencyKey: randomUUID() };
  if (state.inputFingerprint)
    expect(
      state.inputFingerprint,
      "Saved job belongs to different inputs; use another VASTRAVIEW_LIVE_CASE.",
    ).toBe(inputFingerprint);
  else if (
    state.jobId &&
    (process.env.VASTRAVIEW_LIVE_PERSON ||
      process.env.VASTRAVIEW_LIVE_GARMENT ||
      process.env.VASTRAVIEW_LIVE_CATEGORY ||
      process.env.VASTRAVIEW_LIVE_PHOTO_TYPE)
  )
    throw new Error(
      "Existing job has no input fingerprint; preserve it and use a new case name.",
    );
  state.inputFingerprint = inputFingerprint;
  if (existsSync(sessionFile)) {
    await context.addCookies(
      JSON.parse(readFileSync(sessionFile, "utf8")).cookies,
    );
    const refresh = await page.request.post("/api/v1/auth/refresh");
    expect(
      refresh.ok(),
      "Saved live-test session expired; do not submit duplicate inference.",
    ).toBe(true);
  } else {
    expect(
      state.jobId,
      "A saved job needs its original session; do not claim another user's result.",
    ).toBeUndefined();
    const signup = await page.request.post("/api/v1/auth/signup", {
      data: {
        name: "Vastra Live Verification",
        email: `vastra-live-${randomUUID()}@example.com`,
        password: `Live!${randomUUID()}`,
        terms_accepted: true,
      },
    });
    expect(signup.status()).toBe(201);
  }
  await context.storageState({ path: sessionFile });
  writeFileSync(stateFile, JSON.stringify(state));
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  if (!state.jobId) {
    await expect
      .poll(
        async () => {
          const response = await page.request.get("/api/tryon/availability");
          expect(response.ok()).toBe(true);
          return (await response.json()).available;
        },
        {
          timeout: 120000,
          intervals: [3000],
          message:
            "Real model readiness is required before inference; recovery has a bounded wait.",
        },
      )
      .toBe(true);
    const submitted = await page.request.post("/api/tryon", {
      headers: {
        Prefer: "respond-async",
        "Idempotency-Key": state.idempotencyKey,
      },
      multipart: {
        personImage: person,
        garmentImage: garment,
        garmentCategory: category,
        garmentPhotoType: photoType,
        tryonMode: "2d",
      },
    });
    expect(submitted.status(), await submitted.text()).toBe(202);
    state.jobId = (await submitted.json()).jobId;
    expect(state.jobId).toBeTruthy();
    writeFileSync(stateFile, JSON.stringify(state));
  }
  await expect
    .poll(
      async () => {
        const response = await page.request.get(
          `/api/tryon/jobs/${state.jobId}`,
        );
        expect(response.ok()).toBe(true);
        const job = await response.json();
        if (job.status === "failed") throw new Error(JSON.stringify(job.error));
        return job.status;
      },
      { timeout: 180000, intervals: [3000] },
    )
    .toBe("success");
  const job = await (
    await page.request.get(`/api/tryon/jobs/${state.jobId}`)
  ).json();
  writeFileSync(path.join(evidence, "job.json"), JSON.stringify(job, null, 2));
  expect(job.result.renderingMethod).toBe("pretrained-vton");
  expect(job.result.provenance.localGpuUsed).toBe(false);
  const original = await page.request.get(job.result.originalUrl);
  const after = await page.request.get(job.result.previewUrl);
  expect(original.status()).toBe(200);
  expect(after.status()).toBe(200);
  expect(after.headers()["cache-control"]).toBe("no-store");
  const afterBytes = await after.body();
  writeFileSync(path.join(evidence, "original.png"), await original.body());
  writeFileSync(path.join(evidence, "after.png"), afterBytes);
  const history = await (await page.request.get("/api/v1/history")).json();
  expect(
    history.items.some(
      (item: { result?: { previewUrl: string } }) =>
        item.result?.previewUrl === job.result.previewUrl,
    ),
  ).toBe(true);
  const stranger = await newRequest.newContext({
    baseURL: "http://127.0.0.1:5173",
  });
  try {
    expect((await stranger.get(job.result.previewUrl)).status()).toBe(401);
    expect(
      (await stranger.get(`/api/tryon/jobs/${state.jobId}`)).status(),
    ).toBe(401);
  } finally {
    await stranger.dispose();
  }
  let posts = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/api/tryon")) posts++;
  });
  await page.goto(`/tryon?job=${state.jobId}`);
  const viewer = page.getByTestId("viewer");
  await expect(viewer).toHaveAttribute("data-loaded", "true", {
    timeout: 30000,
  });
  await page.reload();
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await expect(
    viewer.getByRole("img", { name: "Generated virtual try-on", exact: true }),
  ).toHaveAttribute("src", job.result.previewUrl);
  await page.getByRole("button", { name: "Side by side", exact: true }).click();
  await page.screenshot({
    path: path.join(evidence, "desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Slider", exact: true }).click();
  await page
    .getByRole("slider", { name: "Before and after comparison slider" })
    .fill("65");
  await viewer.screenshot({ path: path.join(evidence, "slider.png") });
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download render" }).click();
  const downloaded = await (await downloadEvent).path();
  expect(
    createHash("sha256").update(readFileSync(downloaded!)).digest("hex"),
  ).toBe(createHash("sha256").update(afterBytes).digest("hex"));
  await page.route("**/api/tryon/availability", (route) => route.abort());
  await page.reload();
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await page.unroute("**/api/tryon/availability");
  await page.reload();
  await expect(viewer).toHaveAttribute("data-loaded", "true");
  await page.setViewportSize({ width: 375, height: 812 });
  await viewer.screenshot({ path: path.join(evidence, "mobile.png") });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(posts).toBe(0);
  expect(errors).toEqual([]);
  await context.storageState({ path: sessionFile });
});
