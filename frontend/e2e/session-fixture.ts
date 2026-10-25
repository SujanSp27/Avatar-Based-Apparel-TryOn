import { expect, type Page } from "@playwright/test";
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
