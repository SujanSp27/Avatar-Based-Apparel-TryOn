import {
  expect,
  request,
  type Page,
  type BrowserContext,
  test as base,
} from "@playwright/test";
import { randomUUID } from "node:crypto";

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
export function authenticatedSuite(test: typeof base) {
  let cookies: Awaited<ReturnType<BrowserContext["cookies"]>> = [];
  let password = "";
  test.beforeEach(async ({ page, context }) => {
    page.setDefaultTimeout(15000);
    if (cookies.length) await context.addCookies(cookies);
    else password = await signInForTest(page);
  });
  test.afterEach(async ({ context }) => {
    cookies = await context.cookies();
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
