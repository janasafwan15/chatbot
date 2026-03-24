import { apiFetch } from "./http";

export type UserRow = {
  user_id: number;
  username: string;
  role: "admin" | "supervisor" | "employee";
  full_name: string;
  email?: string | null;
  phone?: string | null;
  status: "active" | "inactive";
  last_login?: string | null;  // ✅ جديد
};

export const UsersAPI = {
  list: (token: string) =>
    apiFetch<UserRow[]>("/admin/users", { token }),

  create: (
    token: string,
    body: { username: string; password: string; role: "admin" | "supervisor" | "employee"; full_name: string }
  ) => apiFetch<UserRow>("/admin/users", { token, method: "POST", body }),

  update: (
    token: string,
    user_id: number,
    body: Partial<{ full_name: string; role: "admin" | "supervisor" | "employee"; status: "active" | "inactive"; password: string }>
  ) => apiFetch<UserRow>(`/admin/users/${user_id}`, { token, method: "PUT", body }),

  remove: (token: string, user_id: number) =>
    apiFetch<{ ok: boolean }>(`/admin/users/${user_id}`, { token, method: "DELETE" }),

  resetPassword: (token: string, user_id: number) =>
    apiFetch<{ ok: boolean; temp_password: string }>(`/admin/users/${user_id}/reset-password`, { token, method: "POST" }),
};