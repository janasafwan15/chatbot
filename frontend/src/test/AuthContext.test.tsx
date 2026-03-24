// src/test/AuthContext.test.tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, act } from "@testing-library/react";
import { AuthProvider, useAuth } from "../context/AuthContext";

vi.mock("../api/auth", () => ({
  setMemToken: vi.fn(),
  clearMemToken: vi.fn(),
  getMemToken: vi.fn(() => null),
  isLoggedIn: vi.fn(() => false),
  hasStoredSession: vi.fn(() => false),
  silentRefresh: vi.fn(async () => false),
}));

// Component مساعد لاختبار الـ context
function Inspector({ onCapture }: { onCapture: (v: ReturnType<typeof useAuth>) => void }) {
  const auth = useAuth();
  onCapture(auth);
  return null;
}

describe("AuthContext", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("الـ state الابتدائي فاضي — لا role ولا token", () => {
    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <Inspector onCapture={(v) => { captured = v; }} />
      </AuthProvider>
    );
    expect(captured!.token).toBe("");
    expect(captured!.role).toBeNull();
    expect(captured!.fullName).toBeNull();
    expect(captured!.mustChangePassword).toBe(false);
  });

  it("setAuth يحفظ البيانات في الـ state", () => {
    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <Inspector onCapture={(v) => { captured = v; }} />
      </AuthProvider>
    );

    act(() => {
      captured!.setAuth({
        token: "tok123",
        role: "admin",
        fullName: "محمد علي",
        mustChangePassword: false,
      });
    });

    expect(captured!.token).toBe("tok123");
    expect(captured!.role).toBe("admin");
    expect(captured!.fullName).toBe("محمد علي");
  });

  it("setAuth لا يكتب role أو fullName في localStorage", () => {
    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <Inspector onCapture={(v) => { captured = v; }} />
      </AuthProvider>
    );

    act(() => {
      captured!.setAuth({ token: "t", role: "employee", fullName: "فاطمة" });
    });

    expect(localStorage.getItem("role")).toBeNull();
    expect(localStorage.getItem("fullName")).toBeNull();
  });

  it("logout يُفرّغ كل الـ state", () => {
    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <Inspector onCapture={(v) => { captured = v; }} />
      </AuthProvider>
    );

    act(() => {
      captured!.setAuth({ token: "tok", role: "admin", fullName: "أحمد" });
    });
    act(() => {
      captured!.logout();
    });

    expect(captured!.token).toBe("");
    expect(captured!.role).toBeNull();
    expect(captured!.fullName).toBeNull();
  });

  it("clearMustChangePassword يُصفّر الـ flag", () => {
    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <Inspector onCapture={(v) => { captured = v; }} />
      </AuthProvider>
    );

    act(() => {
      captured!.setAuth({ token: "t", role: "employee", fullName: "x", mustChangePassword: true });
    });
    expect(captured!.mustChangePassword).toBe(true);

    act(() => { captured!.clearMustChangePassword(); });
    expect(captured!.mustChangePassword).toBe(false);
  });
});
