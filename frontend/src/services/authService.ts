import { api, jsonBody } from "./api/client";
import type { Session, User } from "../types/studio";
export const authService = {
  login: (email: string, password: string, remember: boolean) =>
    api<Session>("/api/v1/auth/login", jsonBody({ email, password, remember })),
  signup: (name: string, email: string, password: string) =>
    api<Session>(
      "/api/v1/auth/signup",
      jsonBody({ name, email, password, terms_accepted: true }),
    ),
  logout: () => api<void>("/api/v1/auth/logout", { method: "POST" }),
  update: (name: string, height_cm: number | null) =>
    api<User>("/api/v1/profile", jsonBody({ name, height_cm }, "PATCH")),
  forgot: (email: string) =>
    api<{ message: string }>(
      "/api/v1/auth/forgot-password",
      jsonBody({ email }),
    ),
  reset: (token: string, password: string) =>
    api<{ message: string }>(
      "/api/v1/auth/reset-password",
      jsonBody({ token, password }),
    ),
};
