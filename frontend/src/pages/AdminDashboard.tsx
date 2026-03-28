// src/pages/AdminDashboard.tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  LayoutDashboard,
  Users,
  BarChart3,
  LogOut,
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  Shield,
  Download,
  TrendingUp,
  UserCheck,
  KeyRound,
  Brain,
  MapPin,
  Zap,
  Database,
  RefreshCcw,
  Activity,
  AlertCircle,
  CheckCircle,
  FileCheck,
  Star,
} from "lucide-react";

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";

import { UsersAPI } from "../api/users";
import { StatsAPI, Overview, EmployeesActivityResp, ResponseModesResp, KbUsageResp, QualityResp, ComplaintsSummaryResp } from "../api/stats";
import { AnalyticsAPI } from "../api/stats";
import { downloadBlob } from "../utils/download";
import { getApiBase } from "../api/http";
import { FileApproval } from "./FileApproval";
import { EmployeePerformance } from "./EmployeePerformance";
import { RatingsAnalytics } from "../app/components/RatingsAnalytics";

interface AdminDashboardProps {
  onLogout: () => void;
}

interface User {
  id: number;
  displayName: string;      // "الاسم (username)"
  rawUsername: string;      // username الحقيقي للدخول
  role: string;             // arabic label
  permissions: string[];
  status: "active" | "inactive";
  lastLogin: Date | null;
}

type WeeklyRow = { day: string; استفسارات: number };
type PieRow = { name: string; value: number };

function arabicWeekday(dateISO: string) {
  const d = new Date(dateISO);
  const map = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
  return map[d.getDay()];
}

function mapUsers(rows: any[]): User[] {
  return rows.map((r) => {
    const full = r.full_name || "";
    const uname = r.username || "";
    return {
      id: r.user_id,
      rawUsername: uname,
      displayName: full ? `${full} (${uname})` : uname,
      role: r.role === "admin" ? "مدير" : r.role === "supervisor" ? "مشرف" : "موظف دعم فني",
      permissions:
        r.role === "admin"
          ? ["عرض", "تعديل الردود", "التقارير", "حذف"]
          : r.role === "supervisor"
          ? ["عرض", "تعديل الردود", "التقارير"]
          : ["عرض", "تعديل الردود"],
      status: r.status,
      lastLogin: r.last_login ? new Date(r.last_login) : null,
    };
  });
}

type Theme = "blue" | "green" | "purple" | "orange";

function IconBox({ theme, Icon }: { theme: Theme; Icon: any }) {
  const base = "w-12 h-12 rounded-lg flex items-center justify-center";
  const ib = "w-6 h-6";
  switch (theme) {
    case "blue":
      return (
        <div className={`${base} bg-blue-100`}>
          <Icon className={`${ib} text-blue-600`} />
        </div>
      );
    case "green":
      return (
        <div className={`${base} bg-green-100`}>
          <Icon className={`${ib} text-green-600`} />
        </div>
      );
    case "purple":
      return (
        <div className={`${base} bg-purple-100`}>
          <Icon className={`${ib} text-purple-600`} />
        </div>
      );
    default:
      return (
        <div className={`${base} bg-orange-100`}>
          <Icon className={`${ib} text-orange-600`} />
        </div>
      );
  }
}

export function AdminDashboard({ onLogout }: AdminDashboardProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "users" | "analytics" | "file-approval" | "performance" | "ratings">("overview");

  // ===== Users =====
  const [users, setUsers] = useState<User[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [isAddingNew, setIsAddingNew] = useState(false);

  // ✅ فورم موحد: إضافة + تعديل
  const [editForm, setEditForm] = useState({
    fullName: "",
    loginUsername: "",
    tempPassword: "",
    role: "موظف دعم فني",
    permissions: [] as string[],
    status: "active" as "active" | "inactive",
  });

  // ===== Stats =====
  const { token } = useAuth();
  const [loadingStats, setLoadingStats] = useState(false);
  const [statsError, setStatsError] = useState("");

  const [overview, setOverview] = useState<Overview | null>(null);

  const [weeklyData, setWeeklyData] = useState<WeeklyRow[]>([
    { day: "السبت", استفسارات: 0 },
    { day: "الأحد", استفسارات: 0 },
    { day: "الاثنين", استفسارات: 0 },
    { day: "الثلاثاء", استفسارات: 0 },
    { day: "الأربعاء", استفسارات: 0 },
    { day: "الخميس", استفسارات: 0 },
    { day: "الجمعة", استفسارات: 0 },
  ]);

  const [categoryData, setCategoryData] = useState<PieRow[]>([{ name: "unknown", value: 0 }]);
  const [timeSeriesData, setTimeSeriesData] = useState<WeeklyRow[]>([]);
  const COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6"];

  // ✅ تقرير الموظفين
  const [employeesReport, setEmployeesReport] = useState<EmployeesActivityResp | null>(null);

  // ✅ إحصائيات إضافية
  const [responseModes, setResponseModes] = useState<ResponseModesResp | null>(null);
  const [kbUsage, setKbUsage] = useState<KbUsageResp | null>(null);
  const [quality, setQuality] = useState<QualityResp | null>(null);
  const [complaintsSummary, setComplaintsSummary] = useState<ComplaintsSummaryResp | null>(null);
  const [systemHealth, setSystemHealth] = useState<{ok: boolean; services?: any} | null>(null);

  // ===== Advanced Analytics State =====
  type AdvTab = "problems" | "neighborhoods" | "rag_metrics" | "llm_usage" | "admin_controls";
  const [advTab, setAdvTab] = useState<AdvTab>("problems");
  const [advDays, setAdvDays] = useState(30);
  const [advLoading, setAdvLoading] = useState(false);
  const [advError, setAdvError] = useState("");
  const [advProblems, setAdvProblems] = useState<any>(null);
  const [advNeighborhoods, setAdvNeighborhoods] = useState<any>(null);
  const [advRagMetrics, setAdvRagMetrics] = useState<any>(null);
  const [advLlmUsage, setAdvLlmUsage] = useState<any>(null);
  const [advKbHealth, setAdvKbHealth] = useState<any>(null);
  const [advRebuildStatus, setAdvRebuildStatus] = useState<any>(null);
  const [advRebuildRunning, setAdvRebuildRunning] = useState(false);
  const rebuildPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ===== Load users =====
  useEffect(() => {
    if (!token) return;
    UsersAPI.list(token)
      .then((rows: any[]) => setUsers(mapUsers(rows)))
      .catch(() => {});
  }, [token]);

  // ===== Load stats =====
  useEffect(() => {
    if (!token) return;
    let alive = true;
    setLoadingStats(true);
    setStatsError("");

    // فحص حالة النظام
    fetch(`${getApiBase()}/health-rag`)
      .then(r => r.json())
      .then(d => { if (alive) setSystemHealth(d); })
      .catch(() => { if (alive) setSystemHealth({ ok: false }); });

    Promise.all([
      StatsAPI.overview(token),
      StatsAPI.daily(30, token),
      StatsAPI.topIntents(30, 10, token),
      StatsAPI.peakHours(30, token),
      StatsAPI.employeesActivity(30, token),
      StatsAPI.responseModes(30, token),
      StatsAPI.kbUsage(10, 30, token),
      StatsAPI.quality(30, token),
      StatsAPI.complaintsSummary(30, token),
    ])
      .then(([ov, daily, intents, peak, emp, modes, kb, qual, complaints]) => {
        if (!alive) return;

        setOverview(ov);
        setEmployeesReport(emp);
        setResponseModes(modes);
        setKbUsage(kb);
        setQuality(qual);
        setComplaintsSummary(complaints);

        const last7 = (daily.messages_daily || []).slice(-7);
        const w: WeeklyRow[] = last7.map((r: any) => ({
          day: arabicWeekday(r.day),
          استفسارات: r.messages,
        }));
        if (w.length) setWeeklyData(w);

        const pie: PieRow[] = (intents.top_intents || []).map((x: any) => ({
          name: x.intent || "unknown",
          value: x.total || 0,
        }));
        if (pie.length) setCategoryData(pie);

        const ts: WeeklyRow[] = (peak.hours || []).map((h: any) => ({
          day: `${h.hour}:00`,
          استفسارات: h.total,
        }));
        setTimeSeriesData(ts);
      })
      .catch((e) => {
        if (!alive) return;
        setStatsError(e?.message || "Stats error");
      })
      .finally(() => {
        if (!alive) return;
        setLoadingStats(false);
      });

    return () => {
      alive = false;
    };
  }, [token]);

  // ===== Advanced Analytics Loader =====
  const loadAdvanced = useCallback(async () => {
    if (!token) return;
    setAdvLoading(true);
    setAdvError("");
    try {
      if (advTab === "problems") {
        const [p, n] = await Promise.all([
          AnalyticsAPI.chatProblems(advDays, token),
          AnalyticsAPI.neighborhoodComplaints(advDays, token),
        ]);
        setAdvProblems(p);
        setAdvNeighborhoods(n);
      } else if (advTab === "neighborhoods") {
        const n = await AnalyticsAPI.neighborhoodComplaints(advDays, token);
        setAdvNeighborhoods(n);
      } else if (advTab === "rag_metrics") {
        const r = await AnalyticsAPI.ragEvalMetrics(advDays, token);
        setAdvRagMetrics(r);
      } else if (advTab === "llm_usage") {
        const l = await AnalyticsAPI.llmUsage(advDays * 24, token);
        setAdvLlmUsage(l);
      } else if (advTab === "admin_controls") {
        const [k, s] = await Promise.all([
          AnalyticsAPI.kbHealth(token),
          AnalyticsAPI.rebuildEmbeddingsStatus(token),
        ]);
        setAdvKbHealth(k);
        setAdvRebuildStatus(s);
        setAdvRebuildRunning(s?.running || false);
      }
    } catch (e: any) {
      setAdvError(e.message || "خطأ في التحميل");
    } finally {
      setAdvLoading(false);
    }
  }, [advTab, advDays, token]);

  useEffect(() => {
    if (activeTab === "analytics") loadAdvanced();
  }, [activeTab, loadAdvanced]);

  // Poll rebuild progress — max 150 attempts (5 min) to prevent infinite polling
  useEffect(() => {
    if (rebuildPollRef.current) clearInterval(rebuildPollRef.current);
    if (!advRebuildRunning || !token) return;
    let attempts = 0;
    const MAX_ATTEMPTS = 150;
    rebuildPollRef.current = setInterval(async () => {
      attempts++;
      try {
        const s = await AnalyticsAPI.rebuildEmbeddingsStatus(token);
        setAdvRebuildStatus(s);
        if (!s.running || attempts >= MAX_ATTEMPTS) {
          setAdvRebuildRunning(false);
          clearInterval(rebuildPollRef.current!);
          if (attempts >= MAX_ATTEMPTS) {
            setAdvError("انتهت مهلة متابعة عملية البناء. تحقق من حالة الخادم.");
          }
        }
      } catch {
        if (attempts >= 10) {
          setAdvRebuildRunning(false);
          clearInterval(rebuildPollRef.current!);
          setAdvError("تعذّر الاتصال بالخادم أثناء متابعة عملية البناء.");
        }
      }
    }, 2000);
    return () => { if (rebuildPollRef.current) clearInterval(rebuildPollRef.current); };
  }, [advRebuildRunning, token]);

  const startRebuild = async (overwrite: boolean) => {
    try {
      await AnalyticsAPI.rebuildEmbeddings(overwrite, token);
      setAdvRebuildRunning(true);
      setTimeout(loadAdvanced, 600);
    } catch (e: any) {
      setAdvError(e.message);
    }
  };

  // ===== Helpers =====
  const refreshUsers = async () => {
    const rows = await UsersAPI.list(token);
    setUsers(mapUsers(rows));
  };

  // ===== Handlers =====
  const handleEdit = (user: User) => {
    setEditingId(user.id);
    setIsAddingNew(false);

    // displayName مثل: "أميرة (emp_ameera)" — ناخذ الاسم قبل القوس
    const nameOnly = user.displayName.includes("(")
      ? user.displayName.split("(")[0].trim()
      : user.displayName;

    setEditForm({
      fullName: nameOnly,
      loginUsername: user.rawUsername,
      tempPassword: "", // لا نعرض باسوورد قديم
      role: user.role,
      permissions: user.permissions,
      status: user.status,
    });
  };

  const handleCancel = () => {
    setEditingId(null);
    setIsAddingNew(false);
    setEditForm({
      fullName: "",
      loginUsername: "",
      tempPassword: "",
      role: "موظف دعم فني",
      permissions: [],
      status: "active",
    });
  };

  const handleAddNew = () => {
    setEditingId(null);
    setIsAddingNew(true);
    setEditForm({
      fullName: "",
      loginUsername: "",
      tempPassword: "",
      role: "موظف دعم فني",
      permissions: ["عرض"],
      status: "active",
    });
  };

  const togglePermission = (permission: string) => {
    setEditForm((prev) => ({
      ...prev,
      permissions: prev.permissions.includes(permission)
        ? prev.permissions.filter((p) => p !== permission)
        : [...prev.permissions, permission],
    }));
  };

  const handleSave = async () => {
    try {
      // ===== UPDATE =====
      if (editingId) {
        const fullName = editForm.fullName.trim();
        if (!fullName) {
          alert("الرجاء إدخال الاسم للعرض");
          return;
        }

        const body: any = {
          full_name: fullName,
          status: editForm.status,
          role: editForm.role === "مدير" ? "admin" : editForm.role === "مشرف" ? "supervisor" : "employee",
          // ملاحظة: username ما بنغيره هون (اختياري)
        };

        await UsersAPI.update(token, editingId, body);
        await refreshUsers();

        handleCancel();
        return;
      }

      // ===== CREATE =====
      if (isAddingNew) {
        const fullName = editForm.fullName.trim();
        const usernameForLogin = editForm.loginUsername.trim();
        const tempPassword = editForm.tempPassword.trim();

        if (!fullName) return alert("الرجاء إدخال الاسم للعرض");
        if (!usernameForLogin) return alert("الرجاء إدخال اسم المستخدم للدخول");
        if (!tempPassword || tempPassword.length < 8) return alert("كلمة المرور المؤقتة لازم تكون 8 أحرف على الأقل");

        // تحقق بسيط (اختياري)
        const usernameOk = /^[a-zA-Z0-9_]+$/.test(usernameForLogin);
        if (!usernameOk) {
          alert("اسم المستخدم لازم يكون إنجليزي/أرقام/underscore فقط بدون مسافات");
          return;
        }

        await UsersAPI.create(token, {
          username: usernameForLogin,
          full_name: fullName,
          role: editForm.role === "مدير" ? "admin" : editForm.role === "مشرف" ? "supervisor" : "employee",
          password: tempPassword,
        });

        await refreshUsers();

        alert(`✅ تم إنشاء المستخدم\nUsername: ${usernameForLogin}\nPassword: ${tempPassword}`);

        handleCancel();
      }
    } catch (e: any) {
      alert(e?.message || "فشل حفظ المستخدم");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("هل أنت متأكد من حذف هذا المستخدم؟")) return;
    try {
      await UsersAPI.remove(token, id);
      await refreshUsers();
    } catch (e: any) {
      alert(e?.message || "فشل حذف المستخدم");
    }
  };

  // ✅ Export handlers
  const handleResetPassword = async (user: User) => {
    if (!confirm(`إعادة تعيين كلمة مرور "${user.displayName}"؟\nسيتم تعيينها مؤقتاً وسيُطلب من الموظف تغييرها عند أول دخول.`)) return;
    try {
      const res = await UsersAPI.resetPassword(token, user.id);
      alert(`✅ تم إعادة التعيين\nكلمة المرور المؤقتة: ${res.temp_password}`);
    } catch (e: any) {
      alert(e?.message || "فشل إعادة التعيين");
    }
  };

  const exportMonthlyExcel = async () => {
    try {
      const blob = await StatsAPI.exportMonthlyExcel(30, token);
      downloadBlob(blob, "monthly_report_30d.xlsx");
    } catch (e: any) {
      alert(e?.message || "فشل تصدير Excel");
    }
  };

  const exportMonthlyPDF = async () => {
    try {
      const blob = await StatsAPI.exportMonthlyPDF(30, token);
      downloadBlob(blob, "monthly_report_30d.pdf");
    } catch (e: any) {
      alert(e?.message || "فشل تصدير PDF");
    }
  };
    const exportEmployeesExcel = async () => {
    try {
      const blob = await StatsAPI.exportEmployeesExcel(30, token);
      downloadBlob(blob, "employees_activity_30d.xlsx");
    } catch (e: any) {
      alert(e?.message || "فشل تصدير تقرير الموظفين Excel");
    }
  };

  const exportEmployeesPDF = async () => {
    try {
      const blob = await StatsAPI.exportEmployeesPDF(30, token);
      downloadBlob(blob, "employees_activity_30d.pdf");
    } catch (e: any) {
      alert(e?.message || "فشل تصدير تقرير الموظفين PDF");
    }
  };

  // ✅ Stats cards
  const stats = useMemo(() => {
    const totalMsgs = overview?.total_messages ?? 0;
    const af = Math.round((overview?.answer_found_rate ?? 0) * 100);
    return [
      { label: "إجمالي المستخدمين", value: users.length, icon: Users, theme: "blue" as Theme },
      {
        label: "المستخدمون النشطون",
        value: users.filter((u) => u.status === "active").length,
        icon: TrendingUp,
        theme: "green" as Theme,
      },
      {
        label: "إجمالي الاستفسارات (الشهر)",
        value: totalMsgs.toLocaleString("ar-PS"),
        icon: BarChart3,
        theme: "purple" as Theme,
      },
      { label: "نسبة الإجابة التلقائية", value: `${af}%`, icon: TrendingUp, theme: "orange" as Theme },
    ];
  }, [overview, users]);

  const employeesSummary = useMemo(() => {
    const list = employeesReport?.employees || [];
    const total = list.length;
    const active = list.filter((x) => x.status === "نشط").length;
    const top = list[0] || null;
    return { total, active, top };
  }, [employeesReport]);

  return (
    <div className="flex h-screen bg-gray-50" dir="rtl">
      {/* Sidebar */}
      <div className="w-64 bg-gradient-to-b from-purple-600 to-blue-600 text-white p-6 relative">
        <div className="mb-8">
          <div className="w-12 h-12 bg-white rounded-lg flex items-center justify-center mb-3">
            <Shield className="w-6 h-6 text-purple-600" />
          </div>
          <h2 className="text-xl font-bold">لوحة الإدارة</h2>
          <p className="text-sm text-purple-200">كهرباء الخليل</p>
        </div>

        <nav className="space-y-2">
          <button
            onClick={() => {
              setActiveTab("overview");
              handleCancel();
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "overview" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <LayoutDashboard className="w-5 h-5" />
            <span>لوحة المعلومات</span>
          </button>

          <button
            onClick={() => {
              setActiveTab("users");
              handleCancel();
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "users" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <Users className="w-5 h-5" />
            <span>إدارة المستخدمين</span>
          </button>

          <button
            onClick={() => {
              setActiveTab("analytics");
              handleCancel();
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "analytics" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <BarChart3 className="w-5 h-5" />
            <span>التحليلات المتقدمة</span>
          </button>

          <button
            onClick={() => setActiveTab("file-approval")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "file-approval" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <FileCheck className="w-5 h-5" />
            <span>موافقة الملفات</span>
          </button>

          <button
            onClick={() => setActiveTab("performance")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "performance" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <TrendingUp className="w-5 h-5" />
            <span>أداء الموظفين</span>
          </button>

          <button
            onClick={() => setActiveTab("ratings")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "ratings" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <Star className="w-5 h-5" />
            <span>التقييمات</span>
          </button>
        </nav>

        <button
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-red-500/20 transition-colors absolute bottom-6 right-6 left-6"
        >
          <LogOut className="w-5 h-5" />
          <span>تسجيل الخروج</span>
        </button>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">
              {activeTab === "overview"      && "لوحة المعلومات الرئيسية"}
              {activeTab === "users"         && "إدارة المستخدمين والصلاحيات"}
              {activeTab === "analytics"     && "التحليلات والتقارير المتقدمة"}
              {activeTab === "file-approval" && "موافقة الملفات"}
              {activeTab === "performance"   && "أداء الموظفين"}
              {activeTab === "ratings"       && "التقييمات"}
            </h1>
            <p className="text-gray-600">
              {activeTab === "overview"      && "نظرة شاملة على أداء النظام (نفس تقرير الموظف)"}
              {activeTab === "users"         && "إضافة وتعديل المستخدمين وصلاحياتهم"}
              {activeTab === "analytics"     && "تقرير الأداء + تقرير أداء الموظفين"}
              {activeTab === "file-approval" && "مراجعة والموافقة على الملفات المرفوعة من الموظفين"}
              {activeTab === "performance"   && "تقارير نشاط الموظفين ومساهماتهم في قاعدة المعرفة"}
              {activeTab === "ratings"       && "تحليلات تقييمات المواطنين للمحادثات والرسائل"}
            </p>

            {(loadingStats || statsError) && (
              <div className="mt-3 text-sm">
                {loadingStats ? <span className="text-gray-500">تحميل الإحصائيات…</span> : null}
                {statsError ? <span className="text-red-600">خطأ: {statsError}</span> : null}
              </div>
            )}
          </div>

          {/* Overview */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              {/* Stats */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {stats.map((stat, idx) => (
                  <div key={idx} className="bg-white rounded-xl shadow-md p-6">
                    <div className="flex items-center justify-between mb-4">
                      <IconBox theme={stat.theme} Icon={stat.icon} />
                    </div>
                    <h3 className="text-gray-600 text-sm mb-1">{stat.label}</h3>
                    <p className="text-3xl font-bold text-gray-800">{stat.value}</p>
                  </div>
                ))}
              </div>

              {/* Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-xl font-bold text-gray-800 mb-4">الاستفسارات الأسبوعية</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={weeklyData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="day" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="استفسارات" fill="#3B82F6" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-xl font-bold text-gray-800 mb-4">التوزيع حسب التصنيف</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={categoryData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={(entry: any) => entry.name}
                        outerRadius={80}
                        dataKey="value"
                      >
                        {categoryData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-md p-6">
                <h3 className="text-xl font-bold text-gray-800 mb-4">حالة النظام</h3>
                {systemHealth === null ? (
                  <p className="text-sm text-gray-400">جارٍ الفحص...</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                      { label: "نموذج الذكاء الاصطناعي", key: "ollama_llm" },
                      { label: "نموذج التضمين", key: "embeddings" },
                      { label: "قاعدة البيانات (PostgreSQL)", key: "postgres_db" },
                    ].map(({ label, key }) => {
                      const svc = systemHealth?.services?.[key];
                      const ok = svc?.ok === true;
                      const subtitle = key === "postgres_db" && svc?.db_name ? svc.db_name : null;
                      return (
                        <div key={key} className={`p-4 rounded-lg ${ok ? "bg-green-50" : "bg-red-50"}`}>
                          <div className="flex items-center gap-3 mb-2">
                            <div className={`w-3 h-3 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`} />
                            <span className="font-semibold text-gray-800">{label}</span>
                          </div>
                          <p className={`text-sm ${ok ? "text-green-700" : "text-red-600"}`}>
                            {ok ? "نشط" : (svc ? "لا يستجيب" : "غير متاح")}
                            {svc?.latency_ms ? ` — ${svc.latency_ms}ms` : ""}
                          </p>
                          {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
                          {svc?.error && <p className="text-xs text-red-500 mt-1 truncate" title={svc.error}>{svc.error}</p>}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Users */}
          {activeTab === "users" && (
            <div className="space-y-6">
              {/* Add button */}
              <div className="flex justify-end">
                <button
                  onClick={handleAddNew}
                  disabled={isAddingNew || editingId !== null}
                  className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg flex items-center gap-2 font-semibold transition-colors"
                >
                  <Plus className="w-5 h-5" />
                  إضافة مستخدم جديد
                </button>
              </div>

              {/* Add form */}
              {isAddingNew && (
                <div className="bg-white rounded-xl shadow-md p-6 text-gray-800">
                  <h3 className="text-xl font-bold mb-4">إضافة مستخدم جديد</h3>

                  <div className="space-y-4">
                    <div>
                      <label className="block font-semibold mb-2">الاسم (للعرض)</label>
                      <input
                        type="text"
                        placeholder="مثال: أميرة / جنى"
                        value={editForm.fullName}
                        onChange={(e) => setEditForm({ ...editForm, fullName: e.target.value })}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      />
                    </div>

                    <div>
                      <label className="block font-semibold mb-2">اسم المستخدم (للدخول)</label>
                      <input
                        type="text"
                        placeholder="مثال: emp_ameera"
                        value={editForm.loginUsername}
                        onChange={(e) => setEditForm({ ...editForm, loginUsername: e.target.value })}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      />
                      <p className="text-xs text-gray-500 mt-1">إنجليزي/أرقام/_ فقط، بدون مسافات.</p>
                    </div>

                    <div>
                      <label className="block font-semibold mb-2">كلمة المرور (مؤقتة)</label>
                      <input
                        type="text"
                        value={editForm.tempPassword}
                        onChange={(e) => setEditForm({ ...editForm, tempPassword: e.target.value })}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        الموظف سيُطلب منه تغيير كلمة المرور عند أول تسجيل دخول.
                      </p>
                    </div>

                    <div>
                      <label className="block font-semibold mb-2">الدور الوظيفي</label>
                      <select
                        value={editForm.role}
                        onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      >
                        <option>موظف دعم فني</option>
                        <option>مشرف</option>
                        <option>مدير</option>
                      </select>
                    </div>

                    <div>
                      <label className="block font-semibold mb-2">الصلاحيات</label>
                      <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-600 space-y-1">
                        {editForm.role === "مدير" && (
                          <p>✅ كل الصلاحيات — إدارة المستخدمين، تعديل الردود، التقارير، الحذف</p>
                        )}
                        {editForm.role === "مشرف" && (
                          <p>✅ تعديل الردود + التقارير + التقييمات — بدون إدارة المستخدمين أو الحذف</p>
                        )}
                        {editForm.role === "موظف دعم فني" && (
                          <p>✅ تعديل الردود فقط — بدون تقارير أو حذف</p>
                        )}
                      </div>
                    </div>

                    <div>
                      <label className="block font-semibold mb-2">الحالة</label>
                      <select
                        value={editForm.status}
                        onChange={(e) => setEditForm({ ...editForm, status: e.target.value as "active" | "inactive" })}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      >
                        <option value="active">نشط</option>
                        <option value="inactive">غير نشط</option>
                      </select>
                    </div>

                    <div className="flex gap-3">
                      <button
                        onClick={handleSave}
                        className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg flex items-center gap-2 font-semibold"
                      >
                        <Save className="w-5 h-5" />
                        حفظ
                      </button>
                      <button
                        onClick={handleCancel}
                        className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-6 py-2 rounded-lg flex items-center gap-2 font-semibold"
                      >
                        <X className="w-5 h-5" />
                        إلغاء
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Users list */}
              <div className="space-y-4">
                {users.map((user) => (
                  <div key={user.id} className="bg-white rounded-xl shadow-md p-6">
                    {editingId === user.id ? (
                      <div className="space-y-4 text-gray-800">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <label className="block font-semibold mb-2">الاسم (للعرض)</label>
                            <input
                              type="text"
                              value={editForm.fullName}
                              onChange={(e) => setEditForm({ ...editForm, fullName: e.target.value })}
                              className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                            />
                          </div>

                          <div>
                            <label className="block font-semibold mb-2">الدور الوظيفي</label>
                            <select
                              value={editForm.role}
                              onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                              className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                            >
                              <option>موظف دعم فني</option>
                              <option>مشرف</option>
                              <option>مدير</option>
                            </select>
                          </div>
                        </div>

                        <div>
                          <label className="block font-semibold mb-2">الحالة</label>
                          <select
                            value={editForm.status}
                            onChange={(e) => setEditForm({ ...editForm, status: e.target.value as "active" | "inactive" })}
                            className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                          >
                            <option value="active">نشط</option>
                            <option value="inactive">غير نشط</option>
                          </select>
                        </div>

                        <div className="flex gap-3">
                          <button
                            onClick={handleSave}
                            className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg flex items-center gap-2 font-semibold"
                          >
                            <Save className="w-5 h-5" />
                            حفظ
                          </button>
                          <button
                            onClick={handleCancel}
                            className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-6 py-2 rounded-lg flex items-center gap-2 font-semibold"
                          >
                            <X className="w-5 h-5" />
                            إلغاء
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start justify-between">
                        <div className="flex gap-4 flex-1">
                          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-blue-500 rounded-full flex items-center justify-center text-white font-bold text-xl">
                            {user.displayName?.charAt(0) || "U"}
                          </div>

                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <h4 className="text-lg font-bold text-gray-800">{user.displayName}</h4>
                              <span
                                className={`px-3 py-1 rounded-full text-xs font-semibold ${
                                  user.status === "active"
                                    ? "bg-green-100 text-green-700"
                                    : "bg-gray-100 text-gray-700"
                                }`}
                              >
                                {user.status === "active" ? "نشط" : "غير نشط"}
                              </span>
                            </div>

                            <p className="text-gray-600 mb-2">{user.role}</p>

                            <div className="flex flex-wrap gap-2 mb-2">
                              {user.permissions.map((perm, idx) => (
                                <span
                                  key={idx}
                                  className="bg-purple-50 text-purple-700 text-xs font-semibold px-3 py-1 rounded-full"
                                >
                                  {perm}
                                </span>
                              ))}
                            </div>

                            <p className="text-xs text-gray-400">
                              آخر تسجيل دخول: {user.lastLogin ? user.lastLogin.toLocaleString("ar-PS") : "لم يسجل بعد"}
                            </p>
                          </div>
                        </div>

                        <div className="flex gap-2">
                          <button
                            onClick={() => handleEdit(user)}
                            disabled={editingId !== null || isAddingNew}
                            className="p-2 hover:bg-blue-50 text-blue-600 rounded-lg transition-colors disabled:opacity-50"
                            title="تعديل"
                          >
                            <Edit className="w-5 h-5" />
                          </button>

                          <button
                            onClick={() => handleResetPassword(user)}
                            disabled={editingId !== null || isAddingNew}
                            className="p-2 hover:bg-yellow-50 text-yellow-600 rounded-lg transition-colors disabled:opacity-50"
                            title="إعادة تعيين كلمة المرور"
                          >
                            <KeyRound className="w-5 h-5" />
                          </button>

                          <button
                            onClick={() => handleDelete(user.id)}
                            disabled={editingId !== null || isAddingNew}
                            className="p-2 hover:bg-red-50 text-red-600 rounded-lg transition-colors disabled:opacity-50"
                            title="حذف"
                          >
                            <Trash2 className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Analytics */}
          {activeTab === "analytics" && (
            <div className="space-y-5">

              {/* ── Sub-tab bar ───────────────────────────────── */}
              <div className="bg-white rounded-xl shadow-sm p-3 flex flex-wrap items-center gap-2">
                {(
                  [
                    { id: "problems",        label: "أكثر المشاكل",      icon: Brain },
                    { id: "neighborhoods",   label: "الأحياء الشاكية",   icon: MapPin },
                    { id: "rag_metrics",     label: "جودة RAG",           icon: TrendingUp },
                    { id: "llm_usage",       label: "استهلاك LLM",        icon: Zap },
                    { id: "admin_controls",  label: "Admin Controls",     icon: Database },
                  ] as { id: AdvTab; label: string; icon: any }[]
                ).map(({ id, label, icon: Icon }) => (
                  <button
                    key={id}
                    onClick={() => { setAdvTab(id); setTimeout(loadAdvanced, 50); }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      advTab === id
                        ? "bg-indigo-600 text-white shadow"
                        : "bg-gray-100 text-gray-600 hover:bg-indigo-50 hover:text-indigo-600"
                    }`}
                  >
                    <Icon className="w-4 h-4" /> {label}
                  </button>
                ))}

                {/* Days filter */}
                <div className="mr-auto flex items-center gap-2">
                  <span className="text-xs text-gray-500">الفترة:</span>
                  {[7, 30, 90].map(d => (
                    <button
                      key={d}
                      onClick={() => { setAdvDays(d); setTimeout(loadAdvanced, 50); }}
                      className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                        advDays === d
                          ? "border-indigo-500 bg-indigo-50 text-indigo-700 font-semibold"
                          : "border-gray-200 text-gray-600 hover:border-indigo-300"
                      }`}
                    >
                      {d} يوم
                    </button>
                  ))}
                  <button
                    onClick={loadAdvanced}
                    className="px-3 py-1.5 rounded-lg text-xs border border-gray-200 text-gray-600 hover:bg-gray-50 flex items-center gap-1"
                  >
                    <RefreshCcw className="w-3 h-3" /> تحديث
                  </button>
                </div>
              </div>

              {/* Error */}
              {advError && (
                <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" /> {advError}
                </div>
              )}

              {/* Loading */}
              {advLoading && (
                <div className="bg-white rounded-xl shadow-sm p-10 text-center text-gray-400 text-sm">
                  <Activity className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
                  جاري تحميل البيانات...
                </div>
              )}

              {/* ══════════════════════════════════════════════ */}
              {/* TAB: أكثر المشاكل                             */}
              {/* ══════════════════════════════════════════════ */}
              {!advLoading && advTab === "problems" && advProblems && (
                <>
                  {/* KPIs */}
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: "إجمالي الرسائل",    value: advProblems.total_messages?.toLocaleString("ar-PS"), color: "indigo", bg: "bg-indigo-50",   text: "text-indigo-700",   icon: "💬" },
                      { label: "بدون إجابة",         value: advProblems.unanswered_count?.toLocaleString("ar-PS"), sub: `${advProblems.unanswered_rate}%`, color: "red", bg: "bg-red-50", text: "text-red-700", icon: "❓" },
                      { label: "أكثر مشكلة",         value: (advProblems.top_problems?.[0]?.problem || "—").slice(0, 28), color: "emerald", bg: "bg-emerald-50", text: "text-emerald-700", icon: "🔥" },
                    ].map((k, i) => (
                      <div key={i} className={`${k.bg} rounded-xl p-5 border border-white/50 shadow-sm`}>
                        <p className="text-xs text-gray-500 mb-1">{k.icon} {k.label}</p>
                        <p className={`text-xl font-bold ${k.text}`}>{k.value ?? "—"}</p>
                        {k.sub && <p className="text-xs text-gray-400 mt-0.5">{k.sub} من الإجمالي</p>}
                      </div>
                    ))}
                  </div>

                  {/* Top Problems Chart */}
                  <div className="bg-white rounded-xl shadow-sm p-6">
                    <h3 className="text-base font-bold text-gray-800 mb-4">أكثر المشاكل المطروحة</h3>
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={advProblems.top_problems?.slice(0, 10) || []} layout="vertical" margin={{ right: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" tick={{ fontSize: 11 }} />
                        <YAxis type="category" dataKey="problem" width={170} tick={{ fontSize: 11 }} />
                        <Tooltip
                          formatter={(val: any, _: any, p: any) => [`${val} سؤال`, `حُلّ: ${p.payload?.resolved_pct ?? 0}%`]}
                        />
                        <Bar dataKey="count" fill="#4f46e5" name="عدد الأسئلة" radius={[0, 4, 4, 0]}>
                          {(advProblems.top_problems?.slice(0, 10) || []).map((_: any, i: number) => (
                            <Cell key={i} fill={i === 0 ? "#dc2626" : i < 3 ? "#f59e0b" : "#4f46e5"} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Keywords Cloud */}
                  <div className="bg-white rounded-xl shadow-sm p-6">
                    <h3 className="text-base font-bold text-gray-800 mb-4">أكثر الكلمات المفتاحية في أسئلة المواطنين</h3>
                    <div className="flex flex-wrap gap-2">
                      {(advProblems.top_keywords || []).slice(0, 35).map((kw: any, i: number) => (
                        <span key={i} className={`px-3 py-1 rounded-full text-sm font-medium ${
                          i < 3 ? "bg-red-100 text-red-700 font-bold" :
                          i < 8 ? "bg-indigo-100 text-indigo-700" :
                          "bg-gray-100 text-gray-600"
                        }`}>
                          {kw.word}
                          <span className="text-xs mr-1 opacity-60">({kw.count})</span>
                        </span>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* ══════════════════════════════════════════════ */}
              {/* TAB: الأحياء الشاكية                          */}
              {/* ══════════════════════════════════════════════ */}
              {!advLoading && advTab === "neighborhoods" && advNeighborhoods && (
                <>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: "محادثات محللة",    value: advNeighborhoods.total_analyzed?.toLocaleString("ar-PS"), bg: "bg-blue-50",    text: "text-blue-700",    icon: "🔍" },
                      { label: "أحياء مُعرَّفة",  value: advNeighborhoods.neighborhoods_found, bg: "bg-teal-50",     text: "text-teal-700",    icon: "🏘️" },
                      { label: "أكثر حي شكاوى",   value: (advNeighborhoods.top_neighborhoods?.[0]?.neighborhood || "—").slice(0, 22), bg: "bg-red-50", text: "text-red-700", icon: "📍" },
                    ].map((k, i) => (
                      <div key={i} className={`${k.bg} rounded-xl p-5 shadow-sm`}>
                        <p className="text-xs text-gray-500 mb-1">{k.icon} {k.label}</p>
                        <p className={`text-xl font-bold ${k.text}`}>{k.value ?? "—"}</p>
                      </div>
                    ))}
                  </div>

                  {advNeighborhoods.top_neighborhoods?.length ? (
                    <>
                      <div className="bg-white rounded-xl shadow-sm p-6">
                        <h3 className="text-base font-bold text-gray-800 mb-4">أكثر الأحياء شكاوى</h3>
                        <ResponsiveContainer width="100%" height={300}>
                          <BarChart data={advNeighborhoods.top_neighborhoods.slice(0, 12)} layout="vertical" margin={{ right: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                            <XAxis type="number" tick={{ fontSize: 11 }} />
                            <YAxis type="category" dataKey="neighborhood" width={140} tick={{ fontSize: 11 }} />
                            <Tooltip formatter={(val: any, _: any, p: any) => [val, `أكثر مشكلة: ${p.payload?.top_problem || "—"}`]} />
                            <Bar dataKey="complaints" name="شكاوى" radius={[0, 4, 4, 0]}>
                              {advNeighborhoods.top_neighborhoods.slice(0, 12).map((_: any, i: number) => (
                                <Cell key={i} fill={i === 0 ? "#dc2626" : i < 3 ? "#f59e0b" : "#6366f1"} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>

                      <div className="bg-white rounded-xl shadow-sm p-6 overflow-x-auto">
                        <h3 className="text-base font-bold text-gray-800 mb-4">تفاصيل الأحياء</h3>
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="bg-indigo-600 text-white text-right">
                              <th className="px-4 py-2 rounded-r-lg">الحي / المنطقة</th>
                              <th className="px-4 py-2 text-center">الشكاوى</th>
                              <th className="px-4 py-2 rounded-l-lg">أكثر مشكلة</th>
                            </tr>
                          </thead>
                          <tbody>
                            {advNeighborhoods.top_neighborhoods.map((n: any, i: number) => (
                              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                                <td className="px-4 py-2.5 font-medium text-gray-800">{n.neighborhood}</td>
                                <td className="px-4 py-2.5 text-center font-bold text-red-600">{n.complaints}</td>
                                <td className="px-4 py-2.5 text-gray-600 text-xs">{n.top_problem}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  ) : (
                    <div className="bg-white rounded-xl shadow-sm p-10 text-center text-gray-400">
                      <MapPin className="w-10 h-10 mx-auto mb-3 opacity-30" />
                      <p className="text-sm">لم يُعرَّف أي حي من نصوص المحادثات حتى الآن</p>
                      <p className="text-xs mt-1 text-gray-400">تأكد أن المواطنين يذكرون أسماء أحيائهم في الأسئلة</p>
                    </div>
                  )}
                </>
              )}

              {/* ══════════════════════════════════════════════ */}
              {/* TAB: جودة RAG                                 */}
              {/* ══════════════════════════════════════════════ */}
              {!advLoading && advTab === "rag_metrics" && advRagMetrics && (
                <>
                  {/* Metric Cards */}
                  <div className="grid grid-cols-5 gap-3">
                    {[
                      { label: "Precision@5", val: advRagMetrics.avg_precision, color: "#4f46e5", bg: "bg-indigo-50", text: "text-indigo-700", tip: "من المسترجع كم ذو صلة؟" },
                      { label: "Recall@5",    val: advRagMetrics.avg_recall,    color: "#0891b2", bg: "bg-cyan-50",   text: "text-cyan-700",   tip: "كم استرجعنا من الصحيح؟" },
                      { label: "F1 Score",    val: advRagMetrics.avg_f1,        color: "#059669", bg: "bg-emerald-50",text: "text-emerald-700",tip: "التوازن بين Precision وRecall" },
                      { label: "MRR",         val: advRagMetrics.avg_mrr,       color: "#d97706", bg: "bg-amber-50",  text: "text-amber-700",  tip: "متوسط رتبة أول نتيجة صحيحة" },
                      { label: "Hit@5",       val: advRagMetrics.hit_rate,      color: "#7c3aed", bg: "bg-purple-50", text: "text-purple-700", tip: "هل وُجد جواب في أفضل 5؟" },
                    ].map((m, i) => (
                      <div key={i} title={m.tip} className={`${m.bg} rounded-xl p-4 text-center shadow-sm border border-white/60`}>
                        <p className="text-xs text-gray-500 mb-2">{m.label}</p>
                        <p className={`text-2xl font-bold ${m.text}`}>
                          {advRagMetrics.total_evals > 0 ? `${(m.val * 100).toFixed(1)}%` : "—"}
                        </p>
                        <p className="text-xs text-gray-400 mt-1">{m.tip}</p>
                      </div>
                    ))}
                  </div>

                  {advRagMetrics.total_evals === 0 ? (
                    <div className="bg-white rounded-xl shadow-sm p-10 text-center text-gray-400">
                      <Brain className="w-10 h-10 mx-auto mb-3 opacity-30" />
                      <p className="text-sm">لم يتم تسجيل تقييمات بعد</p>
                      <p className="text-xs mt-1">ستبدأ تلقائياً مع أول محادثة</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-5">
                      {/* Radar */}
                      <div className="bg-white rounded-xl shadow-sm p-6">
                        <h3 className="text-base font-bold text-gray-800 mb-4">نظرة شاملة على جودة الـ RAG</h3>
                        <ResponsiveContainer width="100%" height={240}>
                          <RadarChart data={[
                            { metric: "Precision", value: advRagMetrics.avg_precision * 100 },
                            { metric: "Recall",    value: advRagMetrics.avg_recall * 100 },
                            { metric: "F1",        value: advRagMetrics.avg_f1 * 100 },
                            { metric: "MRR",       value: advRagMetrics.avg_mrr * 100 },
                            { metric: "Hit@5",     value: advRagMetrics.hit_rate * 100 },
                          ]}>
                            <PolarGrid />
                            <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
                            <PolarRadiusAxis domain={[0, 100]} tick={false} />
                            <Radar dataKey="value" stroke="#4f46e5" fill="#4f46e5" fillOpacity={0.25} />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Daily F1 trend */}
                      <div className="bg-white rounded-xl shadow-sm p-6">
                        <h3 className="text-base font-bold text-gray-800 mb-4">اتجاه الجودة اليومي</h3>
                        <ResponsiveContainer width="100%" height={240}>
                          <LineChart data={advRagMetrics.daily || []}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                            <YAxis domain={[0, 1]} tickFormatter={v => `${(+v * 100).toFixed(0)}%`} tick={{ fontSize: 10 }} />
                            <Tooltip formatter={(v: any) => `${(+v * 100).toFixed(1)}%`} />
                            <Legend />
                            <Line type="monotone" dataKey="f1"        stroke="#059669" name="F1"        strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="precision" stroke="#4f46e5" name="Precision" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="recall"    stroke="#0891b2" name="Recall"    strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}

                  <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-xs text-amber-800">
                    💡 هذه المقاييس محسوبة تلقائياً (proxy evaluation). للحصول على دقة أعلى، أضف Ground Truth labels عبر واجهة التقييم.
                  </div>
                </>
              )}

              {/* ══════════════════════════════════════════════ */}
              {/* TAB: استهلاك LLM                              */}
              {/* ══════════════════════════════════════════════ */}
              {!advLoading && advTab === "llm_usage" && advLlmUsage && (
                <>
                  <div className="grid grid-cols-4 gap-4">
                    {[
                      { label: "إجمالي الطلبات",   value: advLlmUsage.total_calls?.toLocaleString("ar-PS"),                        bg: "bg-indigo-50", text: "text-indigo-700", icon: "🤖" },
                      { label: "معدل النجاح",        value: `${advLlmUsage.success_rate}%`,                                           bg: "bg-emerald-50",text: "text-emerald-700",icon: "✅" },
                      { label: "متوسط الاستجابة",   value: `${advLlmUsage.avg_latency_ms}ms`,                                        bg: "bg-amber-50",  text: "text-amber-700",  icon: "⏱️" },
                      { label: "إجمالي Tokens",     value: (advLlmUsage.total_tokens_in + advLlmUsage.total_tokens_out).toLocaleString("ar-PS"), bg: "bg-purple-50", text: "text-purple-700", icon: "🔤" },
                    ].map((k, i) => (
                      <div key={i} className={`${k.bg} rounded-xl p-5 shadow-sm`}>
                        <p className="text-xs text-gray-500 mb-1">{k.icon} {k.label}</p>
                        <p className={`text-xl font-bold ${k.text}`}>{k.value}</p>
                      </div>
                    ))}
                  </div>

                  <div className="bg-white rounded-xl shadow-sm p-6">
                    <h3 className="text-base font-bold text-gray-800 mb-4">الطلبات بالساعة (آخر {advDays * 24} ساعة)</h3>
                    <ResponsiveContainer width="100%" height={240}>
                      <LineChart data={advLlmUsage.hourly || []}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="calls"  stroke="#4f46e5" name="طلبات" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="errors" stroke="#dc2626" name="أخطاء" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Per model */}
                  {Object.keys(advLlmUsage.calls_per_model || {}).length > 0 && (
                    <div className="bg-white rounded-xl shadow-sm p-6">
                      <h3 className="text-base font-bold text-gray-800 mb-4">استهلاك حسب النموذج</h3>
                      <div className="space-y-3">
                        {Object.entries(advLlmUsage.calls_per_model).map(([model, data]: [string, any]) => (
                          <div key={model} className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
                            <div className="w-2 h-2 rounded-full bg-indigo-500" />
                            <span className="text-sm font-medium text-gray-700 flex-1 truncate">{model}</span>
                            <span className="text-sm text-gray-500">{data.calls} طلب</span>
                            <span className="text-xs text-gray-400">{(data.tokens_in + data.tokens_out).toLocaleString()} token</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {advLlmUsage.recent_errors?.length > 0 && (
                    <div className="bg-white rounded-xl shadow-sm p-6">
                      <h3 className="text-base font-bold text-red-700 mb-3 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" /> آخر الأخطاء
                      </h3>
                      <div className="space-y-2">
                        {advLlmUsage.recent_errors.map((e: any, i: number) => (
                          <div key={i} className="flex items-start gap-3 p-2.5 bg-red-50 rounded-lg text-xs text-red-800">
                            <span className="text-gray-400 shrink-0">{e.ts?.slice(0, 19)}</span>
                            <span className="font-medium">{e.model}</span>
                            <span className="flex-1">{e.error}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* ══════════════════════════════════════════════ */}
              {/* TAB: Admin Controls                           */}
              {/* ══════════════════════════════════════════════ */}
              {!advLoading && advTab === "admin_controls" && (
                <>
                  {/* KB Health */}
                  {advKbHealth && (
                    <div className="bg-white rounded-xl shadow-sm p-6">
                      <h3 className="text-base font-bold text-gray-800 mb-4 flex items-center gap-2">
                        <Database className="w-5 h-5 text-indigo-500" /> صحة قاعدة المعرفة (Embeddings)
                      </h3>

                      <div className="grid grid-cols-4 gap-4 mb-5">
                        {[
                          { label: "إجمالي Chunks",     value: advKbHealth.total_chunks,     bg: "bg-indigo-50", text: "text-indigo-700", icon: "📄" },
                          { label: "مع Embeddings",      value: advKbHealth.total_embeddings, bg: "bg-emerald-50",text: "text-emerald-700",icon: "🧠" },
                          { label: "بدون Embeddings",    value: advKbHealth.missing_embeddings,bg: advKbHealth.missing_embeddings > 0 ? "bg-red-50" : "bg-emerald-50", text: advKbHealth.missing_embeddings > 0 ? "text-red-700" : "text-emerald-700", icon: "⚠️" },
                          { label: "نسبة التغطية",       value: `${advKbHealth.coverage_pct}%`,bg: "bg-purple-50",text: "text-purple-700", icon: "📊" },
                        ].map((k, i) => (
                          <div key={i} className={`${k.bg} rounded-xl p-4 text-center shadow-sm`}>
                            <p className="text-xs text-gray-500 mb-1">{k.icon} {k.label}</p>
                            <p className={`text-xl font-bold ${k.text}`}>{k.value}</p>
                          </div>
                        ))}
                      </div>

                      {/* Coverage bar */}
                      <div className="mb-5">
                        <div className="flex justify-between text-xs text-gray-500 mb-1">
                          <span>تغطية الـ Embeddings</span>
                          <span>{advKbHealth.coverage_pct}%</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-3">
                          <div
                            className={`h-3 rounded-full transition-all duration-500 ${advKbHealth.coverage_pct >= 90 ? "bg-emerald-500" : advKbHealth.coverage_pct >= 50 ? "bg-amber-500" : "bg-red-500"}`}
                            style={{ width: `${advKbHealth.coverage_pct}%` }}
                          />
                        </div>
                      </div>

                      {advKbHealth.missing_embeddings > 0 && (
                        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 mb-5 flex items-center gap-2">
                          <AlertCircle className="w-4 h-4 shrink-0" />
                          يوجد <strong className="mx-1">{advKbHealth.missing_embeddings}</strong> مستند بدون embeddings — إعادة البناء مطلوبة
                        </div>
                      )}

                      {/* Rebuild buttons */}
                      <div className="flex flex-wrap gap-3 mb-5">
                        <button
                          onClick={() => startRebuild(false)}
                          disabled={advRebuildRunning}
                          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          <RefreshCcw className={`w-4 h-4 ${advRebuildRunning ? "animate-spin" : ""}`} />
                          بناء المفقود فقط
                        </button>
                        <button
                          onClick={() => {
                            if (!confirm("هذا سيُعيد بناء كل الـ Embeddings من الصفر. تأكيد؟")) return;
                            startRebuild(true);
                          }}
                          disabled={advRebuildRunning}
                          className="flex items-center gap-2 px-5 py-2.5 rounded-lg border-2 border-red-500 text-red-600 hover:bg-red-50 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          <RefreshCcw className="w-4 h-4" /> إعادة بناء الكل
                        </button>
                      </div>

                      {/* Rebuild Progress */}
                      {advRebuildStatus && (
                        <div className="border border-gray-200 rounded-xl p-4 bg-gray-50">
                          <div className="flex items-center gap-2 mb-3">
                            {advRebuildStatus.running
                              ? <Activity className="w-4 h-4 text-indigo-500 animate-spin" />
                              : advRebuildStatus.errors > 0
                              ? <AlertCircle className="w-4 h-4 text-amber-500" />
                              : <CheckCircle className="w-4 h-4 text-emerald-500" />
                            }
                            <span className="text-sm font-semibold text-gray-700">
                              {advRebuildStatus.running
                                ? "جاري البناء..."
                                : advRebuildStatus.finished_at
                                ? `اكتمل — ${advRebuildStatus.done} chunk`
                                : "لم تبدأ أي عملية بعد"}
                            </span>
                            {advRebuildStatus.finished_at && (
                              <span className="text-xs text-gray-400 mr-auto">
                                {advRebuildStatus.finished_at?.slice(0, 19)}
                              </span>
                            )}
                          </div>

                          {advRebuildStatus.total > 0 && (
                            <>
                              <div className="w-full bg-gray-200 rounded-full h-2.5 mb-2">
                                <div
                                  className="h-2.5 rounded-full bg-indigo-500 transition-all duration-300"
                                  style={{ width: `${advRebuildStatus.progress_pct}%` }}
                                />
                              </div>
                              <div className="flex gap-5 text-xs text-gray-500">
                                <span>الكل: <strong className="text-gray-700">{advRebuildStatus.total}</strong></span>
                                <span>تم: <strong className="text-emerald-700">{advRebuildStatus.done}</strong></span>
                                <span>أخطاء: <strong className="text-red-600">{advRebuildStatus.errors}</strong></span>
                                <span className="mr-auto font-semibold text-indigo-600">{advRebuildStatus.progress_pct}%</span>
                              </div>
                            </>
                          )}

                          {advRebuildStatus.last_error && (
                            <p className="text-xs text-red-600 mt-2 bg-red-50 p-2 rounded">
                              آخر خطأ: {advRebuildStatus.last_error}
                            </p>
                          )}
                        </div>
                      )}

                      {/* Chunks without embeddings preview */}
                      {advKbHealth.chunks_without_embeddings?.length > 0 && (
                        <div className="mt-5">
                          <p className="text-sm font-semibold text-gray-700 mb-2">مستندات بدون Embeddings (أول 100):</p>
                          <div className="max-h-48 overflow-y-auto space-y-1.5">
                            {advKbHealth.chunks_without_embeddings.map((c: any, i: number) => (
                              <div key={i} className="flex items-start gap-3 p-2 bg-white border border-gray-100 rounded-lg text-xs">
                                <span className="text-gray-400 shrink-0 font-mono">{c.chunk_id}</span>
                                <span className="text-gray-500 shrink-0">{c.source_file}</span>
                                <span className="text-gray-600 truncate">{c.preview}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Empty state if no data yet */}
                  {!advKbHealth && !advLoading && (
                    <div className="bg-white rounded-xl shadow-sm p-10 text-center text-gray-400">
                      <Database className="w-10 h-10 mx-auto mb-3 opacity-30" />
                      <p className="text-sm">لا توجد بيانات — اضغط تحديث</p>
                    </div>
                  )}
                </>
              )}

              {/* ── الإحصائيات الأصلية (الموجودة مسبقاً) ──────── */}
              {!advLoading && advTab === "problems" && (
                <>
                  {/* الاستفسارات حسب الوقت */}
                  <div className="bg-white rounded-xl shadow-sm p-6">
                    <h3 className="text-base font-bold text-gray-800 mb-4">الاستفسارات حسب الوقت (ذروة الساعة)</h3>
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart data={timeSeriesData.length ? timeSeriesData : weeklyData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="استفسارات" stroke="#8B5CF6" strokeWidth={2} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* أوضاع الردود */}
                  {responseModes?.response_modes?.length ? (
                    <div className="bg-white rounded-xl shadow-sm p-6">
                      <h3 className="text-base font-bold text-gray-800 mb-4">أوضاع الردود (Response Modes)</h3>
                      <div className="space-y-2.5">
                        {responseModes.response_modes.map((m) => {
                          const total = responseModes.response_modes.reduce((s, x) => s + x.total, 0);
                          const pct = total ? Math.round((m.total / total) * 100) : 0;
                          return (
                            <div key={m.mode} className="flex items-center gap-3">
                              <span className="w-36 text-sm text-gray-600 text-right truncate">{m.mode}</span>
                              <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                                <div className="bg-purple-500 h-3 rounded-full transition-all" style={{ width: `${pct}%` }} />
                              </div>
                              <span className="w-24 text-xs font-semibold text-gray-700 text-left">{m.total.toLocaleString("ar-PS")} ({pct}%)</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}

                  {/* استخدام قاعدة المعرفة */}
                  {kbUsage?.kb_usage?.length ? (
                    <div className="bg-white rounded-xl shadow-sm p-6 overflow-x-auto">
                      <h3 className="text-base font-bold text-gray-800 mb-4">أكثر ملفات قاعدة المعرفة استخداماً</h3>
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-right text-gray-500 border-b">
                            <th className="py-2 font-semibold">#</th>
                            <th className="py-2 font-semibold">الملف / المصدر</th>
                            <th className="py-2 font-semibold">عدد الاستخدامات</th>
                          </tr>
                        </thead>
                        <tbody>
                          {kbUsage.kb_usage.map((k, idx) => (
                            <tr key={k.source_file} className="border-b hover:bg-gray-50 transition-colors">
                              <td className="py-2 text-gray-400">{idx + 1}</td>
                              <td className="py-2 font-medium text-gray-800">{k.source_file}</td>
                              <td className="py-2 text-indigo-600 font-bold">{k.total.toLocaleString("ar-PS")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}

                  {/* جودة الردود */}
                  <div className="bg-white rounded-xl shadow-sm p-6">
                    <h3 className="text-base font-bold text-gray-800 mb-4">جودة الردود (آخر 30 يوم)</h3>
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between p-4 bg-emerald-50 rounded-lg">
                          <span className="text-sm text-gray-600">نسبة العثور على إجابة</span>
                          <span className="text-xl font-bold text-emerald-700">
                            {quality ? `${(quality.answer_found_rate * 100).toFixed(1)}%` : "—"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                          <span className="text-sm text-gray-600">متوسط أفضل تطابق</span>
                          <span className="text-xl font-bold text-blue-700">
                            {quality ? quality.avg_best_score.toFixed(2) : "—"}
                          </span>
                        </div>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-gray-700 mb-2">توزيع درجات التطابق</p>
                        {quality?.best_score_buckets?.length ? (
                          <div className="space-y-1.5">
                            {quality.best_score_buckets.map((b) => (
                              <div key={b.bucket} className="flex items-center gap-2 text-sm">
                                <span className="w-16 text-gray-500 text-xs">{b.bucket}</span>
                                <span className="font-semibold text-gray-800">{b.total.toLocaleString("ar-PS")} رسالة</span>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  {/* ملخص الشكاوى */}
                  {complaintsSummary && complaintsSummary.total_complaints > 0 && (
                    <div className="bg-white rounded-xl shadow-sm p-6">
                      <h3 className="text-base font-bold text-gray-800 mb-4">ملخص الشكاوى (آخر 30 يوم)</h3>
                      <div className="flex items-center gap-6 mb-4">
                        <div className="p-4 bg-red-50 rounded-lg text-center">
                          <p className="text-2xl font-bold text-red-700">{complaintsSummary.total_complaints}</p>
                          <p className="text-xs text-gray-500">إجمالي الشكاوى</p>
                        </div>
                        <div className="p-4 bg-orange-50 rounded-lg flex-1">
                          <p className="font-bold text-orange-700">{complaintsSummary.top_complaint}</p>
                          <p className="text-xs text-gray-500 mt-1">أكثر شكوى</p>
                        </div>
                      </div>
                      {complaintsSummary.breakdown?.length ? (
                        <div className="space-y-2">
                          {complaintsSummary.breakdown.map((b) => (
                            <div key={b.category} className="flex items-center gap-3">
                              <span className="flex-1 text-sm text-gray-700 truncate">{b.category}</span>
                              <div className="w-32 bg-gray-100 rounded-full h-2.5 overflow-hidden">
                                <div className="bg-red-400 h-2.5 rounded-full" style={{ width: `${b.percent}%` }} />
                              </div>
                              <span className="w-24 text-xs text-gray-500 text-left">{b.total} ({b.percent}%)</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  )}

                  {/* تصدير التقارير */}
                  <div className="bg-white rounded-xl shadow-sm p-6">
                    <h3 className="text-base font-bold text-gray-800 mb-4">تصدير التقارير</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 border border-gray-100 rounded-xl bg-gray-50">
                        <h4 className="font-semibold text-gray-800 mb-1">تقرير شهري شامل</h4>
                        <p className="text-xs text-gray-500 mb-3">يتضمن جميع الإحصائيات والتحليلات</p>
                        <div className="flex gap-2">
                          <button onClick={exportMonthlyExcel} className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 rounded-lg flex items-center justify-center gap-1.5 text-sm font-semibold transition-colors">
                            <Download className="w-4 h-4" /> Excel
                          </button>
                          <button onClick={exportMonthlyPDF} className="flex-1 bg-red-600 hover:bg-red-700 text-white px-3 py-2 rounded-lg flex items-center justify-center gap-1.5 text-sm font-semibold transition-colors">
                            <Download className="w-4 h-4" /> PDF
                          </button>
                        </div>
                      </div>
                      <div className="p-4 border border-gray-100 rounded-xl bg-gray-50">
                        <h4 className="font-semibold text-gray-800 mb-1">تقرير أداء الموظفين</h4>
                        <p className="text-xs text-gray-500 mb-3">نشاط الموظفين خلال آخر 30 يوم</p>
                        <div className="flex gap-2">
                          <button onClick={exportEmployeesExcel} className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 rounded-lg flex items-center justify-center gap-1.5 text-sm font-semibold transition-colors">
                            <Download className="w-4 h-4" /> Excel
                          </button>
                          <button onClick={exportEmployeesPDF} className="flex-1 bg-red-600 hover:bg-red-700 text-white px-3 py-2 rounded-lg flex items-center justify-center gap-1.5 text-sm font-semibold transition-colors">
                            <Download className="w-4 h-4" /> PDF
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              )}

            </div>
          )}

          {/* موافقة الملفات */}
          {activeTab === "file-approval" && <FileApproval />}

          {/* أداء الموظفين */}
          {activeTab === "performance" && (
            <div className="bg-white rounded-xl shadow-md p-6">
              <EmployeePerformance />
            </div>
          )}

          {/* التقييمات */}
          {activeTab === "ratings" && (
            <div className="bg-white rounded-xl shadow-md p-6">
              <h2 className="text-xl font-bold text-gray-800 mb-6">تحليلات التقييمات</h2>
              <RatingsAnalytics token={token} days={30} showDetails />
            </div>
          )}

        </div>
      </div>
    </div>
  );
}