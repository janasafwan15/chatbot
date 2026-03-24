// frontend/src/api/auth.ts
// ✅ access token في memory فقط — لا يُلمس localStorage أبداً
// ✅ refresh_token في sessionStorage فقط (يُمسح عند إغلاق التاب)
// ✅ role و fullName يُديرهم AuthContext في React state — لا يُخزَّنان في أي storage

import { apiFetch } from "./http";

export type Role = "admin" | "supervisor" | "employee" | "citizen";

export type LoginResponse = {
  token: string;
  refresh_token: string;
  role: Role;
  full_name: string;
  must_change_password: boolean;
};

// ─── In-memory access token ───────────────────────────────────
let _memToken: string | null = null;
let _refreshToken: string | null = null;
let _refreshTimer: ReturnType<typeof setTimeout> | null = null;

export function setMemToken(token: string): void { _memToken = token; }
export function getMemToken(): string | null      { return _memToken; }
export function clearMemToken(): void             { _memToken = null; }

// ─── Refresh token persistence (sessionStorage) ───────────────
// sessionStorage يُمسح عند إغلاق التاب — أأمن من localStorage
const RT_KEY = "rt";

function _saveRefreshToken(rt: string): void {
  _refreshToken = rt;
  try { sessionStorage.setItem(RT_KEY, rt); } catch { /* private mode */ }
}

function _loadRefreshToken(): string | null {
  if (_refreshToken) return _refreshToken;
  try { return sessionStorage.getItem(RT_KEY); } catch { return null; }
}

function _clearRefreshToken(): void {
  _refreshToken = null;
  try { sessionStorage.removeItem(RT_KEY); } catch { /* */ }
}

// ─── Auto-refresh scheduler ───────────────────────────────────
const REFRESH_BEFORE_MS = 5 * 60 * 1000;
const SESSION_HOURS     = 24;

function _scheduleRefresh(): void {
  if (_refreshTimer) clearTimeout(_refreshTimer);
  if (!_refreshToken) return;

  const delay = SESSION_HOURS * 60 * 60 * 1000 - REFRESH_BEFORE_MS;
  _refreshTimer = setTimeout(async () => {
    await silentRefresh();
  }, Math.max(delay, 10_000));
}

// ─── Silent refresh ───────────────────────────────────────────
export async function silentRefresh(): Promise<boolean> {
  const rt = _loadRefreshToken();
  if (!rt) return false;

  try {
    const res = await apiFetch<{ token: string; refresh_token?: string }>(
      "/auth/refresh",
      { method: "POST", body: { refresh_token: rt } }
    );
    if (res?.token) {
      setMemToken(res.token);
      if (res.refresh_token) _saveRefreshToken(res.refresh_token);
      _scheduleRefresh();
      return true;
    }
  } catch {
    clearMemToken();
    _clearRefreshToken();
  }
  return false;
}

// ─── Login ───────────────────────────────────────────────────
export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  const res = await apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: { username, password },
  });

  setMemToken(res.token);
  _saveRefreshToken(res.refresh_token);
  _scheduleRefresh();

  // ✅ role و fullName لا يُخزَّنان هنا — AuthContext يأخذهم من LoginResponse

  return res;
}

// ─── Logout ──────────────────────────────────────────────────
export async function logout(): Promise<void> {
  const token = getMemToken();
  if (_refreshTimer) clearTimeout(_refreshTimer);
  try {
    if (token) {
      await apiFetch("/auth/logout", { method: "POST", token });
    }
  } catch {
    // تجاهل أخطاء الشبكة عند الخروج
  } finally {
    clearMemToken();
    _clearRefreshToken();
  }
}

// ─── Helpers ─────────────────────────────────────────────────
export function isLoggedIn(): boolean {
  return _memToken !== null;
}

export function hasStoredSession(): boolean {
  return _loadRefreshToken() !== null;
}

// ─── Change Password ─────────────────────────────────────────
export async function changePassword(
  old_password: string,
  new_password: string
): Promise<void> {
  const token = getMemToken();
  if (!token) throw new Error("Not authenticated");
  return apiFetch("/auth/change-password", {
    method: "POST",
    token,
    body: { old_password, new_password },
  });
}
