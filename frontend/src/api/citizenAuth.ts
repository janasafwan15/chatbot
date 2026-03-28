/**
 * citizenAuth.ts
 * ──────────────
 * واجهة برمجية لنظام التحقق من هوية المواطن
 * تتحدث مع: /citizen/* endpoints في الـ backend
 */

import { getApiBase } from "./http";

// ── Types ──────────────────────────────────────────────────────

export interface RequestOtpResponse {
  success: boolean;
  message: string;
  masked_phone: string;
  expires_in: number;
  dev_otp?: string; // للتجربة فقط — يُزال في الإنتاج
}

export interface VerifyOtpResponse {
  success: boolean;
  citizen_token: string;
  expires_in: number;
  full_name: string;
  message: string;
}

export interface CitizenAccount {
  full_name: string;
  national_id: string;
  phone: string;
  address: string;
  meter_number: string;
  account_number: string;
  subscription_type: string;
  subscription_status: string;
  connection_date: string;
  balance: number;
  unpaid_total: number;
  last_invoice: Invoice | null;
}

export interface Invoice {
  invoice_id: string;
  period: string;
  issue_date: string;
  due_date: string;
  amount: number;
  status: string;
  consumption_kwh: number;
}

export interface InvoicesResponse {
  success: boolean;
  account_number: string;
  meter_number: string;
  invoices: Invoice[];
  summary: {
    total_invoices: number;
    unpaid_count: number;
    unpaid_amount: number;
    paid_count: number;
  };
}

export interface BalanceResponse {
  success: boolean;
  meter_number: string;
  account_number: string;
  balance: number;
  status_message: string;
  subscription_status: string;
  last_invoice: Invoice | null;
}

// ── API Helpers ───────────────────────────────────────────────

async function post<T>(path: string, body: object): Promise<T> {
  const base = getApiBase();
  const res = await fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.detail || `HTTP ${res.status}`);
  }
  return data as T;
}

// ── Citizens Auth Service ─────────────────────────────────────

export const citizenAuthService = {
  /** الخطوة 1: المواطن يُدخل رقم هويته */
  async requestOtp(nationalId: string): Promise<RequestOtpResponse> {
    return post<RequestOtpResponse>("/citizen/request-otp", {
      national_id: nationalId,
    });
  },

  /** الخطوة 2: المواطن يُدخل الرمز */
  async verifyOtp(nationalId: string, otpCode: string): Promise<VerifyOtpResponse> {
    return post<VerifyOtpResponse>("/citizen/verify-otp", {
      national_id: nationalId,
      otp_code: otpCode,
    });
  },

  /** جلب بيانات الحساب الكاملة */
  async getAccount(citizenToken: string): Promise<{ success: boolean; account: CitizenAccount }> {
    return post("/citizen/account", { citizen_token: citizenToken });
  },

  /** قائمة الفواتير */
  async getInvoices(citizenToken: string): Promise<InvoicesResponse> {
    return post<InvoicesResponse>("/citizen/invoices", { citizen_token: citizenToken });
  },

  /** الرصيد والعداد */
  async getBalance(citizenToken: string): Promise<BalanceResponse> {
    return post<BalanceResponse>("/citizen/balance", { citizen_token: citizenToken });
  },

  /** تسجيل الخروج */
  async logout(citizenToken: string): Promise<void> {
    await post("/citizen/logout", { citizen_token: citizenToken }).catch(() => {});
  },
};