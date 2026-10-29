import {
  expect,
  request,
  type Page,
  type BrowserContext,
  test as base,
} from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

// Real account/session for transport and layout tests. Inference itself is
// intercepted by those tests; authentication is never mocked away.
export async function signInForTest(page: Page) {
  const password = `Browser!${randomUUID()}`;
  const response = await page.request.post("/api/v1/auth/signup", {
    data: {
      name: "Browser Verification",
      email: `browser-${randomUUID()}@example.com`,
      password,
      terms_accepted: true,
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  return password;
}

// Reuse one real account per file, preserving rotating cookies between isolated
// browser contexts. Layout tests must not consume the production signup quota.
export function authenticatedSuite(
  test: typeof base,
  existingSession?: string,
) {
  // Explicit opt-in for repeated layout checks. Reuse an evaluation account
  // without bypassing refresh validation or deleting an existing account.
  // Do not run the evaluator concurrently with tests using its rotating cookies.
  const sessionPath = existingSession
    ? path.resolve("..", existingSession)
    : undefined;
  if (sessionPath) {
    const relative = path.relative(path.resolve("../.runtime"), sessionPath);
    if (
      relative.startsWith("..") ||
      path.isAbsolute(relative) ||
      !relative.endsWith(".json")
    ) {
      throw new Error(
        "Existing test session must be a private .runtime JSON file",
      );
    }
  }
  let cookies: Awaited<ReturnType<BrowserContext["cookies"]>> = [];
  let password = "";
  test.beforeEach(async ({ page, context }) => {
    page.setDefaultTimeout(15000);
    if (!cookies.length && sessionPath) {
      cookies = JSON.parse(readFileSync(sessionPath, "utf8")).cookies;
      if (!Array.isArray(cookies) || !cookies.length)
        throw new Error("Saved test session is empty");
    }
    if (cookies.length) await context.addCookies(cookies);
    else password = await signInForTest(page);
  });
  test.afterEach(async ({ context }) => {
    // A test can finish just after navigation or opening a second tab while
    // AuthProvider is still rotating the HttpOnly cookie. Capture only after
    // the app's real rotation lock completes; otherwise the next context
    // reuses a revoked token and correctly gets redirected to sign-in.
    await Promise.all(
      context.pages().map(async (page) => {
        if (page.isClosed()) return;
        await page.evaluate(async () => {
          if (navigator.locks)
            await navigator.locks.request("formfit-session-refresh", () => {});
        });
      }),
    );
    cookies = await context.cookies();
    if (sessionPath) {
      const saved = JSON.parse(readFileSync(sessionPath, "utf8"));
      writeFileSync(
        sessionPath,
        JSON.stringify({ ...saved, cookies }, null, 2),
      );
    }
  });
  test.afterAll(async () => {
    if (!password || !cookies.length) return;
    const api = await request.newContext({
      baseURL: "http://127.0.0.1:5173",
      storageState: { cookies, origins: [] },
    });
    try {
      await api.delete("/api/v1/profile", { data: { password } });
    } finally {
      await api.dispose();
      cookies = [];
      password = "";
    }
  });
}
