import type { Session } from "../../types/studio";

let accessToken: string | null = null;
let refreshing: Promise<Session | null> | null = null;
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export function setAccessToken(token: string | null) {
  accessToken = token;
}
export async function errorMessage(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (typeof body?.error?.message === "string") return body.error.message;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail))
    return body.detail
      .map(
        (item: { msg?: string; loc?: string[] }) =>
          `${item.loc?.slice(1).join(" ") || "Input"}: ${item.msg || "Invalid value"}`,
      )
      .join(". ");
  return "Something went wrong. Please try again.";
}
export function refreshSession(): Promise<Session | null> {
  if (!refreshing) {
    const rotate = async (): Promise<Session | null> => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 25000);
      try {
        const response = await fetch("/api/v1/auth/refresh", {
          method: "POST",
          credentials: "include",
          signal: controller.signal,
        });
        if (response.status === 401) {
          accessToken = null;
          return null;
        }
        if (!response.ok)
          throw new ApiError(await errorMessage(response), response.status);
        const session: Session = await response.json();
        accessToken = session.access_token;
        return session;
      } catch (error) {
        if (error instanceof ApiError) throw error;
        throw new ApiError(
          "Could not restore your session. Check your connection and retry.",
          0,
        );
      } finally {
        clearTimeout(timer);
      }
    };
    // Serialize cookie rotation across tabs as well as concurrent requests in this tab.
    refreshing = (
      navigator.locks
        ? navigator.locks.request("formfit-session-refresh", rotate)
        : rotate()
    ).finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}
export async function apiResponse(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    path.includes("extract") ? 90000 : 25000,
  );
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers,
      credentials: "include",
      signal: init.signal
        ? AbortSignal.any([init.signal, controller.signal])
        : controller.signal,
    });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError(
      "Connection interrupted. Check that the app service is running and retry.",
      0,
    );
  } finally {
    clearTimeout(timer);
  }
  if (response.status === 401 && retry && !path.includes("/auth/")) {
    const session = await refreshSession();
    if (session) return apiResponse(path, init, false);
    window.dispatchEvent(new Event("formfit:session-expired"));
  }
  if (!response.ok)
    throw new ApiError(await errorMessage(response), response.status);
  return response;
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiResponse(path, init);
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
export const jsonBody = (value: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(value),
});
