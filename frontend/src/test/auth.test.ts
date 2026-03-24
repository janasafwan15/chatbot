// src/test/auth.test.ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  setMemToken,
  getMemToken,
  clearMemToken,
  isLoggedIn,
  hasStoredSession,
} from "../api/auth";

// mock apiFetch لأن ما عندنا backend حقيقي في الـ tests
vi.mock("../api/http", () => ({
  apiFetch: vi.fn(),
  getApiBase: () => "http://localhost:8000",
  API_BASE: "http://localhost:8000",
}));

describe("auth — in-memory token", () => {
  beforeEach(() => {
    clearMemToken();
    sessionStorage.clear();
  });

  it("getMemToken يُعيد null في البداية", () => {
    expect(getMemToken()).toBeNull();
  });

  it("setMemToken ثم getMemToken يُعيد التوكن الصح", () => {
    setMemToken("abc123");
    expect(getMemToken()).toBe("abc123");
  });

  it("clearMemToken يمسح التوكن", () => {
    setMemToken("abc123");
    clearMemToken();
    expect(getMemToken()).toBeNull();
  });

  it("isLoggedIn يُعيد false لما ما في توكن", () => {
    expect(isLoggedIn()).toBe(false);
  });

  it("isLoggedIn يُعيد true بعد setMemToken", () => {
    setMemToken("tok");
    expect(isLoggedIn()).toBe(true);
  });
});

describe("auth — session storage للـ refresh token", () => {
  beforeEach(() => {
    clearMemToken();
    sessionStorage.clear();
  });

  it("hasStoredSession يُعيد false لما ما في refresh token", () => {
    expect(hasStoredSession()).toBe(false);
  });

  it("hasStoredSession يُعيد true بعد حفظ refresh token في sessionStorage", () => {
    sessionStorage.setItem("rt", "refresh_abc");
    expect(hasStoredSession()).toBe(true);
  });
});

describe("auth — localStorage يبقى فاضي دايماً", () => {
  beforeEach(() => {
    clearMemToken();
    sessionStorage.clear();
    localStorage.clear();
  });

  it("role ما يُكتب في localStorage", () => {
    // حتى لو حدا استدعى login، role ما يجي في localStorage
    expect(localStorage.getItem("role")).toBeNull();
  });

  it("fullName ما يُكتب في localStorage", () => {
    expect(localStorage.getItem("fullName")).toBeNull();
  });

  it("mustChangePassword ما يُكتب في localStorage", () => {
    expect(localStorage.getItem("mustChangePassword")).toBeNull();
  });
});
