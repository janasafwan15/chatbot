// frontend/src/api/http.ts
export const API_BASE_STORAGE_KEY = "api_base";

export function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "") || "http://127.0.0.1:8000";
}

export function getApiBase(): string {
  const fromStorage = localStorage.getItem(API_BASE_STORAGE_KEY);
  if (fromStorage?.trim()) return normalizeBaseUrl(fromStorage);
  return normalizeBaseUrl(import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000");
}

export function setApiBase(url: string): void {
  localStorage.setItem(API_BASE_STORAGE_KEY, normalizeBaseUrl(url));
}

export const API_BASE = getApiBase();

export async function apiFetch<T>(
  path: string,
  opts?: { token?: string; method?: string; body?: unknown }
): Promise<T> {
  // ✅ جيب التوكن من memory تلقائياً لو ما انعطى صريح
  let authToken = opts?.token;
  if (!authToken) {
    const { getMemToken } = await import("./auth");
    authToken = getMemToken() ?? undefined;
  }

  const base = getApiBase();
  const res = await fetch(`${base}${path}`, {
    method: opts?.method ?? (opts?.body ? "POST" : "GET"),
    headers: {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    body: opts?.body ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }

  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return undefined as T;
  return (await res.json()) as T;
}