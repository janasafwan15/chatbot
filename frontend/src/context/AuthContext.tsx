// frontend/src/context/AuthContext.tsx
// ✅ role و fullName في React state فقط — صفر localStorage
// ✅ عند إعادة تحميل الصفحة: silentRefresh يُعيد session إذا في refresh_token محفوظ
//    والـ backend يُعيد role+fullName مع الـ refresh response

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { Role } from "../api/auth";
import { setMemToken, clearMemToken, silentRefresh, isLoggedIn, hasStoredSession } from "../api/auth";

type AuthCtx = {
  token: string;
  role: Role | null;
  fullName: string | null;
  mustChangePassword: boolean;
  setAuth: (d: {
    token: string;
    role: Role;
    fullName: string;
    mustChangePassword?: boolean;
  }) => void;
  clearMustChangePassword: () => void;
  logout: () => void;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken]           = useState("");
  const [role, setRole]             = useState<Role | null>(null);   // ✅ لا localStorage
  const [fullName, setFullName]     = useState<string>("");          // ✅ لا localStorage
  const [mustChangePassword, setMustChangePassword] = useState(false);

  // ── عند تحميل الصفحة: إذا في refresh_token محفوظ → حاول تجديد الجلسة ──
  useEffect(() => {
    if (!isLoggedIn() && hasStoredSession()) {
      silentRefresh().then(async (ok) => {
        if (ok) {
          const { getMemToken } = await import("../api/auth");
          const newToken = getMemToken();
          if (newToken) setToken(newToken);
          // ملاحظة: role و fullName يحتاجون يجوا مع الـ refresh response من الـ backend.
          // إذا الـ backend ما يُعيدهم، اعمل route محمي يجيب /auth/me بعد الـ refresh.
        }
        // إذا فشل الـ refresh — الـ state يبقى فاضي والمستخدم يروح لصفحة الدخول تلقائياً
      });
    }
  }, []);

  const value = useMemo<AuthCtx>(
    () => ({
      token,
      role,
      fullName: fullName || null,
      mustChangePassword,
      setAuth: ({ token, role, fullName, mustChangePassword = false }) => {
        setToken(token);
        setMemToken(token);
        // ✅ كل شيء في React state — صفر localStorage
        setRole(role);
        setFullName(fullName);
        setMustChangePassword(mustChangePassword);
      },
      clearMustChangePassword: () => {
        setMustChangePassword(false);
      },
      logout: () => {
        setToken("");
        clearMemToken();
        setRole(null);
        setFullName("");
        setMustChangePassword(false);
      },
    }),
    [token, role, fullName, mustChangePassword]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}
