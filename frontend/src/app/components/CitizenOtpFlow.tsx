/**
 * CitizenOtpFlow.tsx
 * ──────────────────
 * مكوّن التحقق من هوية المواطن يظهر داخل المحادثة كـ "بطاقة".
 * 
 * المراحل:
 *   idle        → زر "ابدأ التحقق"
 *   enter_id    → إدخال رقم الهوية
 *   enter_otp   → إدخال رمز OTP
 *   verified    → تم التحقق، عرض خيارات البيانات
 *   loading     → انتظار استجابة الـ API
 */

import { useState, useRef, useEffect } from "react";
import {
  ShieldCheck,
  Smartphone,
  KeyRound,
  Loader2,
  CheckCircle2,
  AlertCircle,
  User,
  FileText,
  Wallet,
  Building2,
  LogOut,
} from "lucide-react";
import { citizenAuthService , CitizenAccount, Invoice, InvoicesResponse, BalanceResponse }  from "../../api/citizenAuth";
// ── Types ──────────────────────────────────────────────────────

type FlowStep = "idle" | "enter_id" | "enter_otp" | "loading" | "verified";

interface CitizenSession {
  token: string;
  full_name: string;
  national_id: string;
}

interface CitizenOtpFlowProps {
  /** استدعاء لإرسال بيانات كرسالة بوت إلى المحادثة */
  onDataReady: (text: string) => void;
  /** بيانات الجلسة الحالية (إن كانت موجودة) */
  existingSession?: CitizenSession | null;
  /** تحديث الجلسة في المكوّن الأب */
  onSessionChange: (session: CitizenSession | null) => void;
}

// ── Helpers ───────────────────────────────────────────────────

function formatCurrency(amount: number): string {
  const abs = Math.abs(amount);
  return `${abs.toFixed(2)} ₪`;
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString("ar-PS", {
      year: "numeric", month: "long", day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function statusColor(status: string): string {
  if (status === "مسدد")        return "bg-green-100 text-green-700";
  if (status === "غير مسدد")   return "bg-red-100 text-red-700";
  if (status === "نشط")         return "bg-green-100 text-green-700";
  if (status.includes("موقوف")) return "bg-amber-100 text-amber-700";
  return "bg-gray-100 text-gray-600";
}

// ── Main Component ─────────────────────────────────────────────

export function CitizenOtpFlow({ onDataReady, existingSession, onSessionChange }: CitizenOtpFlowProps) {
  const [step, setStep]             = useState<FlowStep>(existingSession ? "verified" : "idle");
  const [nationalId, setNationalId] = useState("");
  const [otpCode, setOtpCode]       = useState("");
  const [maskedPhone, setMaskedPhone] = useState("");
  const [devOtp, setDevOtp]           = useState<string | null>(null); // للتجربة فقط
  const [error, setError]           = useState<string | null>(null);
  const [session, setSession]       = useState<CitizenSession | null>(existingSession ?? null);

  // عرض البيانات
  const [activeView, setActiveView] = useState<"menu" | "account" | "invoices" | "balance" | "loading_data">("menu");
  const [accountData, setAccountData]   = useState<CitizenAccount | null>(null);
  const [invoicesData, setInvoicesData] = useState<InvoicesResponse | null>(null);
  const [balanceData, setBalanceData]   = useState<BalanceResponse | null>(null);

  const idRef  = useRef<HTMLInputElement>(null);
  const otpRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (step === "enter_id") idRef.current?.focus();
    if (step === "enter_otp") otpRef.current?.focus();
  }, [step]);

  const setErr = (msg: string) => { setError(msg); setTimeout(() => setError(null), 5000); };

  // ── Step handlers ──────────────────────────────────────────

  const handleRequestOtp = async () => {
    const id = nationalId.trim();
    if (!id || id.length < 9) { setErr("أدخل رقم هوية صحيح (9 أرقام على الأقل)"); return; }
    setStep("loading"); setError(null);
    try {
      const res = await citizenAuthService.requestOtp(id);
      setMaskedPhone(res.masked_phone);
      if (res.dev_otp) setDevOtp(res.dev_otp); // للتجربة فقط
      setStep("enter_otp");
    } catch (e: any) {
      setErr(e.message || "تعذّر إرسال الرمز");
      setStep("enter_id");
    }
  };

  const handleVerifyOtp = async () => {
    const code = otpCode.trim();
    if (!code || code.length < 4) { setErr("أدخل الرمز المكوّن من 6 أرقام"); return; }
    setStep("loading"); setError(null);
    try {
      const res = await citizenAuthService.verifyOtp(nationalId.trim(), code);
      const newSession: CitizenSession = {
        token: res.citizen_token,
        full_name: res.full_name,
        national_id: nationalId.trim(),
      };
      setSession(newSession);
      onSessionChange(newSession);
      setDevOtp(null);
      setStep("verified");
      setActiveView("menu");
    } catch (e: any) {
      setErr(e.message || "الرمز غير صحيح");
      setStep("enter_otp");
    }
  };

  const handleLogout = async () => {
    if (session) await citizenAuthService.logout(session.token);
    setSession(null);
    onSessionChange(null);
    setStep("idle");
    setNationalId("");
    setOtpCode("");
    setAccountData(null);
    setInvoicesData(null);
    setBalanceData(null);
    setActiveView("menu");
  };

  // ── Data fetchers ──────────────────────────────────────────

  const fetchAccount = async () => {
    if (!session) return;
    setActiveView("loading_data");
    try {
      const res = await citizenAuthService.getAccount(session.token);
      setAccountData(res.account);
      setActiveView("account");
      // أرسل ملخص كرسالة بوت
      const bal = res.account.balance;
      const balText = bal >= 0 ? `رصيد دائن: ${formatCurrency(bal)} ✅` : `مبلغ مستحق: ${formatCurrency(bal)} ⚠️`;
      onDataReady(
        `📋 **معلومات حسابك**\n\n` +
        `الاسم: ${res.account.full_name}\n` +
        `رقم العداد: ${res.account.meter_number}\n` +
        `نوع الاشتراك: ${res.account.subscription_type}\n` +
        `الحالة: ${res.account.subscription_status}\n` +
        `${balText}\n` +
        `المبلغ غير المسدد: ${formatCurrency(res.account.unpaid_total)}`
      );
    } catch (e: any) {
      setErr(e.message); setActiveView("menu");
    }
  };

  const fetchInvoices = async () => {
    if (!session) return;
    setActiveView("loading_data");
    try {
      const res = await citizenAuthService.getInvoices(session.token);
      setInvoicesData(res);
      setActiveView("invoices");
      const unpaid = res.summary.unpaid_amount;
      onDataReady(
        `🧾 **فواتيرك**\n\n` +
        `رقم الحساب: ${res.account_number}\n` +
        `رقم العداد: ${res.meter_number}\n` +
        `عدد الفواتير: ${res.summary.total_invoices}\n` +
        `غير مسدد: ${res.summary.unpaid_count} فواتير (${formatCurrency(unpaid)})\n` +
        `مسدد: ${res.summary.paid_count} فواتير`
      );
    } catch (e: any) {
      setErr(e.message); setActiveView("menu");
    }
  };

  const fetchBalance = async () => {
    if (!session) return;
    setActiveView("loading_data");
    try {
      const res = await citizenAuthService.getBalance(session.token);
      setBalanceData(res);
      setActiveView("balance");
      onDataReady(
        `💳 **رصيدك**\n\n` +
        `رقم العداد: ${res.meter_number}\n` +
        `${res.status_message}\n` +
        `حالة الاشتراك: ${res.subscription_status}`
      );
    } catch (e: any) {
      setErr(e.message); setActiveView("menu");
    }
  };

  // ── Render helpers ─────────────────────────────────────────

  const Card = ({ children }: { children: React.ReactNode }) => (
    <div className="bg-white border border-blue-100 rounded-2xl p-4 shadow-sm mt-2 max-w-sm">
      {children}
    </div>
  );

  const ErrorBanner = () => error ? (
    <div className="flex items-start gap-2 bg-red-50 text-red-700 text-xs rounded-lg p-2.5 mt-2">
      <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
      <span>{error}</span>
    </div>
  ) : null;

  // ── IDLE ──────────────────────────────────────────────────
  if (step === "idle") return (
    <Card>
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck className="w-5 h-5 text-blue-600" />
        <span className="text-sm font-semibold text-gray-800">التحقق من الهوية</span>
      </div>
      <p className="text-xs text-gray-500 mb-3 leading-relaxed">
        للاطلاع على بياناتك الشخصية (الفواتير، الرصيد، معلومات الحساب) يلزم التحقق من هويتك أولاً.
      </p>
      <button
        onClick={() => setStep("enter_id")}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors"
      >
        ابدأ التحقق من الهوية
      </button>
    </Card>
  );

  // ── ENTER ID ──────────────────────────────────────────────
  if (step === "enter_id") return (
    <Card>
      <div className="flex items-center gap-2 mb-3">
        <User className="w-5 h-5 text-blue-600" />
        <span className="text-sm font-semibold text-gray-800">أدخل رقم هويتك</span>
      </div>
      <p className="text-xs text-gray-500 mb-3">رقم الهوية الوطنية أو رقم الجواز المسجّل في النظام</p>
      <input
        ref={idRef}
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={12}
        value={nationalId}
        onChange={e => setNationalId(e.target.value.replace(/\D/g, ""))}
        onKeyDown={e => e.key === "Enter" && handleRequestOtp()}
        placeholder="مثال: 9871234567"
        className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-right focus:outline-none focus:ring-2 focus:ring-blue-400 mb-2"
        dir="ltr"
      />
      <ErrorBanner />
      <button
        onClick={handleRequestOtp}
        disabled={nationalId.length < 9}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors mt-2"
      >
        إرسال رمز التحقق
      </button>
      <button onClick={() => setStep("idle")} className="w-full text-xs text-gray-400 hover:text-gray-600 mt-2 py-1">
        إلغاء
      </button>
    </Card>
  );

  // ── LOADING ───────────────────────────────────────────────
  if (step === "loading") return (
    <Card>
      <div className="flex items-center gap-3 py-2">
        <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
        <span className="text-sm text-gray-600">جاري المعالجة...</span>
      </div>
    </Card>
  );

  // ── ENTER OTP ─────────────────────────────────────────────
  if (step === "enter_otp") return (
    <Card>
      <div className="flex items-center gap-2 mb-3">
        <Smartphone className="w-5 h-5 text-blue-600" />
        <span className="text-sm font-semibold text-gray-800">أدخل رمز التحقق</span>
      </div>
      <p className="text-xs text-gray-500 mb-1">
        تم إرسال رمز مكوّن من 6 أرقام إلى الهاتف:
        <span className="font-bold text-gray-700 mx-1 dir-ltr inline-block" dir="ltr">{maskedPhone}</span>
      </p>

      {/* ⚠️ للتجربة فقط — يُزال في الإنتاج */}
      {devOtp && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3 text-xs">
          <span className="text-amber-700 font-semibold">🧪 وضع التجربة — الرمز: </span>
          <span className="font-mono font-bold text-amber-800 text-sm">{devOtp}</span>
        </div>
      )}

      {/* OTP boxes */}
      <input
        ref={otpRef}
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={6}
        value={otpCode}
        onChange={e => setOtpCode(e.target.value.replace(/\D/g, ""))}
        onKeyDown={e => e.key === "Enter" && handleVerifyOtp()}
        placeholder="_ _ _ _ _ _"
        className="w-full border border-gray-300 rounded-xl px-4 py-3 text-center text-lg tracking-widest font-mono focus:outline-none focus:ring-2 focus:ring-blue-400 mb-2"
        dir="ltr"
      />
      <ErrorBanner />
      <button
        onClick={handleVerifyOtp}
        disabled={otpCode.length < 6}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors mt-2"
      >
        <span className="flex items-center justify-center gap-2">
          <KeyRound className="w-4 h-4" />
          تحقق
        </span>
      </button>
      <button
        onClick={() => { setOtpCode(""); setStep("enter_id"); }}
        className="w-full text-xs text-gray-400 hover:text-gray-600 mt-2 py-1"
      >
        تغيير رقم الهوية
      </button>
    </Card>
  );

  // ── VERIFIED — menu & data views ─────────────────────────
  if (step === "verified" && session) {

    if (activeView === "loading_data") return (
      <Card>
        <div className="flex items-center gap-3 py-2">
          <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
          <span className="text-sm text-gray-600">جاري جلب البيانات...</span>
        </div>
      </Card>
    );

    // ── Account View ──────────────────────────────────────
    if (activeView === "account" && accountData) return (
      <Card>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-semibold text-gray-800">معلومات الحساب</span>
          </div>
          <button onClick={() => setActiveView("menu")} className="text-xs text-gray-400 hover:text-gray-600">← رجوع</button>
        </div>
        <div className="space-y-2 text-sm">
          {[
            ["الاسم", accountData.full_name],
            ["رقم الهوية", accountData.national_id],
            ["الهاتف", accountData.phone],
            ["العنوان", accountData.address],
            ["رقم العداد", accountData.meter_number],
            ["رقم الحساب", accountData.account_number],
            ["نوع الاشتراك", accountData.subscription_type],
            ["تاريخ التوصيل", formatDate(accountData.connection_date)],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-2 border-b border-gray-50 pb-1.5">
              <span className="text-gray-500 text-xs">{label}</span>
              <span className="text-gray-800 font-medium text-xs text-left" dir="auto">{value}</span>
            </div>
          ))}
          <div className="flex justify-between gap-2 border-b border-gray-50 pb-1.5">
            <span className="text-gray-500 text-xs">الحالة</span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusColor(accountData.subscription_status)}`}>
              {accountData.subscription_status}
            </span>
          </div>
          <div className="flex justify-between gap-2 pt-1">
            <span className="text-gray-500 text-xs">الرصيد</span>
            <span className={`text-sm font-bold ${accountData.balance >= 0 ? "text-green-600" : "text-red-600"}`}>
              {accountData.balance >= 0 ? "+" : "-"}{formatCurrency(accountData.balance)}
            </span>
          </div>
          {accountData.unpaid_total > 0 && (
            <div className="bg-red-50 rounded-lg p-2 text-xs text-red-700 text-center">
              ⚠️ مبلغ غير مسدد: {formatCurrency(accountData.unpaid_total)}
            </div>
          )}
        </div>
      </Card>
    );

    // ── Invoices View ─────────────────────────────────────
    if (activeView === "invoices" && invoicesData) return (
      <Card>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-semibold text-gray-800">الفواتير</span>
          </div>
          <button onClick={() => setActiveView("menu")} className="text-xs text-gray-400 hover:text-gray-600">← رجوع</button>
        </div>

        <div className="grid grid-cols-3 gap-2 mb-3 text-center">
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-base font-bold text-gray-800">{invoicesData.summary.total_invoices}</div>
            <div className="text-xs text-gray-500">الكل</div>
          </div>
          <div className="bg-red-50 rounded-lg p-2">
            <div className="text-base font-bold text-red-600">{invoicesData.summary.unpaid_count}</div>
            <div className="text-xs text-red-500">غير مسدد</div>
          </div>
          <div className="bg-green-50 rounded-lg p-2">
            <div className="text-base font-bold text-green-600">{invoicesData.summary.paid_count}</div>
            <div className="text-xs text-green-500">مسدد</div>
          </div>
        </div>

        {invoicesData.summary.unpaid_amount > 0 && (
          <div className="bg-red-50 border border-red-100 rounded-lg px-3 py-2 mb-3 text-xs text-red-700 text-center font-semibold">
            إجمالي غير مسدد: {formatCurrency(invoicesData.summary.unpaid_amount)}
          </div>
        )}

        <div className="space-y-2 max-h-60 overflow-y-auto">
          {invoicesData.invoices.map((inv: Invoice) => (
            <div key={inv.invoice_id} className="border border-gray-100 rounded-xl p-3">
              <div className="flex justify-between items-start">
                <span className="text-xs text-gray-500">{inv.period}</span>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusColor(inv.status)}`}>
                  {inv.status}
                </span>
              </div>
              <div className="flex justify-between mt-1.5">
                <span className="text-xs text-gray-500">الاستهلاك: {inv.consumption_kwh} كيلوواط</span>
                <span className="text-sm font-bold text-gray-800">{formatCurrency(inv.amount)}</span>
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                استحقاق: {formatDate(inv.due_date)}
              </div>
            </div>
          ))}
        </div>
      </Card>
    );

    // ── Balance View ──────────────────────────────────────
    if (activeView === "balance" && balanceData) return (
      <Card>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Wallet className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-semibold text-gray-800">الرصيد والعداد</span>
          </div>
          <button onClick={() => setActiveView("menu")} className="text-xs text-gray-400 hover:text-gray-600">← رجوع</button>
        </div>

        <div className={`rounded-2xl p-4 text-center mb-3 ${balanceData.balance >= 0 ? "bg-green-50" : "bg-red-50"}`}>
          <div className={`text-3xl font-bold mb-1 ${balanceData.balance >= 0 ? "text-green-600" : "text-red-600"}`}>
            {balanceData.balance >= 0 ? "+" : "-"}{formatCurrency(balanceData.balance)}
          </div>
          <div className={`text-xs ${balanceData.balance >= 0 ? "text-green-600" : "text-red-600"}`}>
            {balanceData.status_message}
          </div>
        </div>

        <div className="space-y-2 text-sm">
          {[
            ["رقم العداد", balanceData.meter_number],
            ["رقم الحساب", balanceData.account_number],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-2 border-b border-gray-50 pb-1.5">
              <span className="text-gray-500 text-xs">{label}</span>
              <span className="text-gray-800 font-medium text-xs" dir="ltr">{value}</span>
            </div>
          ))}
          <div className="flex justify-between gap-2">
            <span className="text-gray-500 text-xs">حالة الاشتراك</span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusColor(balanceData.subscription_status)}`}>
              {balanceData.subscription_status}
            </span>
          </div>
        </div>

        {balanceData.last_invoice && (
          <div className="mt-3 bg-gray-50 rounded-xl p-3">
            <div className="text-xs text-gray-500 mb-1">آخر فاتورة</div>
            <div className="flex justify-between">
              <span className="text-xs text-gray-600">{balanceData.last_invoice.period}</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusColor(balanceData.last_invoice.status)}`}>
                {balanceData.last_invoice.status}
              </span>
            </div>
            <div className="flex justify-between mt-1">
              <span className="text-xs text-gray-500">{balanceData.last_invoice.consumption_kwh} كيلوواط</span>
              <span className="text-sm font-bold text-gray-800">{formatCurrency(balanceData.last_invoice.amount)}</span>
            </div>
          </div>
        )}
      </Card>
    );

    // ── Menu View (default after verification) ────────────
    return (
      <Card>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-green-500" />
            <div>
              <div className="text-sm font-semibold text-gray-800">{session.full_name}</div>
              <div className="text-xs text-gray-400">تم التحقق من هويتك ✓</div>
            </div>
          </div>
          <button onClick={handleLogout} title="تسجيل الخروج" className="text-gray-300 hover:text-red-400 transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {[
            { icon: Building2,  label: "حسابي",   action: fetchAccount  },
            { icon: FileText,   label: "فواتيري",  action: fetchInvoices },
            { icon: Wallet,     label: "رصيدي",    action: fetchBalance  },
          ].map(({ icon: Icon, label, action }) => (
            <button
              key={label}
              onClick={action}
              className="flex flex-col items-center gap-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-xl py-3 transition-colors"
            >
              <Icon className="w-5 h-5" />
              <span className="text-xs font-semibold">{label}</span>
            </button>
          ))}
        </div>
        <ErrorBanner />
      </Card>
    );
  }

  return null;
}