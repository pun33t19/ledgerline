// Small fetch wrapper. The session cookie (set by /api/session) is sent automatically.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { "content-type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new ApiError(response.status, (await response.text()) || response.statusText);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

/**
 * `ledgerline ui` prints a link with ?token=…. Exchange it for a session cookie once,
 * then remove it from the address bar so it isn't left in history or screenshots.
 */
export async function claimTokenFromUrl(): Promise<void> {
  const url = new URL(window.location.href);
  const token = url.searchParams.get("token");
  if (!token) return;
  await api<void>("/api/session", { method: "POST", body: JSON.stringify({ token }) });
  url.searchParams.delete("token");
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
}
