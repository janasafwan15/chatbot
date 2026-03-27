// src/pages/EmployeeDashboard.tsx
import { useEffect, useMemo, useState } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  BarChart3,
  LogOut,
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  TrendingUp,
  CheckCircle,
  Star,
  Download,
  RefreshCw,
  Upload,
  HelpCircle,
} from "lucide-react";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend,
} from "recharts";

import {
  listKnowledge,
  createKnowledge,
  updateKnowledge,
  deleteKnowledge,
  KnowledgeItem as KBItem,
  KnowledgeCreate,
} from "../api/knowledge";

import { StatsAPI, Overview, ResponseModesResp, KbUsageResp, QualityResp } from "../api/stats";
import { useAuth } from "../context/AuthContext";
import { getMemToken } from "../api/auth";
import { RatingsAnalytics } from "../app/components/RatingsAnalytics";
import { FileManagement } from "./FileManagement";
import { UnansweredQuestions } from "./UnansweredQuestions";
import { downloadBlob } from "../utils/download";

interface EmployeeDashboardProps {
  onLogout: () => void;
}

type UIKnowledgeItem = {
  id: number;
  question: string;
  answer: string;
  category: string;
  updatedAt: Date;
  is_active: boolean;
  intent_code?: string | null;
};

type WeeklyRow = { day: string; استفسارات: number };
type PieRow = { name: string; value: number };

function arabicWeekday(dateISO: string) {
  const d = new Date(dateISO);
  const map = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
  return map[d.getDay()];
}

const COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#14B8A6", "#A855F7", "#64748B"];

export function EmployeeDashboard({ onLogout }: EmployeeDashboardProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "responses" | "reports" | "ratings" | "files" | "unanswered">("overview");

  // ✅ FIX: التوكن من memory وليس localStorage
  const { role } = useAuth();
  const token = useMemo(() => getMemToken() ?? "", []);

  // صلاحيات الـ role
  const canManageResponses = role === "employee" || role === "supervisor" || role === "admin";
  const canViewReports     = role === "supervisor" || role === "admin";
  const canDelete          = role === "supervisor" || role === "admin";

  // =========================
  // ✅ KB CRUD
  // =========================
  const [knowledgeItems, setKnowledgeItems] = useState<UIKnowledgeItem[]>([]);
  const [loadingKB, setLoadingKB] = useState(false);
  const [kbError, setKbError] = useState("");

  const [editingId, setEditingId] = useState<number | null>(null);
  const [isAddingNew, setIsAddingNew] = useState(false);

  const [editForm, setEditForm] = useState({
    category: "استفسارات عامة",
    question: "",
    answer: "",
    is_active: true,
    intent_code: "" as string,
  });

  const [syncingRAG, setSyncingRAG] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");

  const syncKBToRAG = async () => {
    setSyncingRAG(true);
    setSyncMsg("");
    try {
      const data = await import("../api/http").then(m =>
        m.apiFetch<{ ok: boolean; synced: number; removed: number; errors: string[] }>(
          "/kb/sync-to-rag",
          { token, method: "POST" }
        )
      );
      if (data.ok) {
        setSyncMsg(`✅ تم المزامنة: ${data.synced} رد متاح للذكاء الاصطناعي`);
      } else {
        setSyncMsg("❌ فشل المزامنة");
      }
    } catch (e: any) {
      setSyncMsg(`❌ ${e?.message || "خطأ في الاتصال"}`);
    } finally {
      setSyncingRAG(false);
      setTimeout(() => setSyncMsg(""), 5000);
    }
  };

  const refreshKB = async () => {
    setLoadingKB(true);
    setKbError("");
    try {
      const rows = await listKnowledge(token);
      const mapped: UIKnowledgeItem[] = rows.map((r: KBItem) => ({
        id: r.kb_id,
        question: r.title_ar,
        answer: r.content_ar,
        category: r.category || "استفسارات عامة",
        updatedAt: new Date(),
        is_active: r.is_active,
        intent_code: r.intent_code ?? null,
      }));
      setKnowledgeItems(mapped);
    } catch (e: any) {
      setKbError(e?.message || "فشل تحميل الردود");
    } finally {
      setLoadingKB(false);
    }
  };

  useEffect(() => {
    refreshKB();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const startAddNew = () => {
    setEditingId(null);
    setIsAddingNew(true);
    setEditForm({
      category: "استفسارات عامة",
      question: "",
      answer: "",
      is_active: true,
      intent_code: "",
    });
  };

  const startEdit = (item: UIKnowledgeItem) => {
    setIsAddingNew(false);
    setEditingId(item.id);
    setEditForm({
      category: item.category || "استفسارات عامة",
      question: item.question,
      answer: item.answer,
      is_active: item.is_active,
      intent_code: item.intent_code || "",
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsAddingNew(false);
    setEditForm({
      category: "استفسارات عامة",
      question: "",
      answer: "",
      is_active: true,
      intent_code: "",
    });
  };

  const saveKB = async () => {
    try {
      const payload: KnowledgeCreate = {
        title_ar: editForm.question.trim(),
        content_ar: editForm.answer.trim(),
        category: editForm.category,
        intent_code: editForm.intent_code.trim() ? editForm.intent_code.trim() : null,
        external_links: null,
        is_active: editForm.is_active,
      };

      if (!payload.title_ar || !payload.content_ar) {
        alert("لازم تعبّي السؤال والإجابة");
        return;
      }

      if (editingId) await updateKnowledge(token, editingId, payload);
      else if (isAddingNew) await createKnowledge(token, payload);

      await refreshKB();
      cancelEdit();
    } catch (e: any) {
      alert(e?.message || "فشل الحفظ");
    }
  };

  const removeKB = async (id: number) => {
    if (!confirm("هل أنت متأكد من الحذف؟")) return;
    try {
      await deleteKnowledge(token, id);
      await refreshKB();
    } catch (e: any) {
      alert(e?.message || "فشل الحذف");
    }
  };

  // =========================
  // ✅ Stats
  // =========================
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [statsError, setStatsError] = useState("");

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

  // Complaints
  const [complaintsData, setComplaintsData] = useState<PieRow[]>([{ name: "لا توجد شكاوى", value: 0 }]);
  const [complaintsTotal, setComplaintsTotal] = useState<number>(0);
  const [complaintsTable, setComplaintsTable] = useState<Array<{ category: string; total: number; percent: number }>>([]);

  // low-rated conversations
  const [lowRatedConversations, setLowRatedConversations] = useState<
    Array<{
      conversation_id: number;
      avg_stars: number;
      ratings_count: number;
      last_rated_at: string;
      preview: Array<{
        message_type: string;
        message_text: string | null;
        response_text: string | null;
        created_at: string;
      }>;
    }>
  >([]);

  // ✅ إحصائيات إضافية
  const [responseModes, setResponseModes] = useState<ResponseModesResp | null>(null);
  const [kbUsage, setKbUsage] = useState<KbUsageResp | null>(null);
  const [quality, setQuality] = useState<QualityResp | null>(null);

  useEffect(() => {
    let alive = true;

    setLoadingStats(true);
    setStatsError("");

    Promise.all([
      StatsAPI.overview(token),
      StatsAPI.daily(30, token),
      StatsAPI.topIntents(30, 10, token),
      StatsAPI.peakHours(30, token),
      StatsAPI.lowRatedConversations(30, 2, 50, token),
      StatsAPI.responseModes(30, token),
      StatsAPI.kbUsage(10, 30, token),
      StatsAPI.quality(30, token),
    ])
      .then(([ov, daily, intents, peak, lowRated, modes, kb, qual]) => {
        if (!alive) return;

        setOverview(ov);
        setLowRatedConversations(lowRated.items || []);
        setResponseModes(modes);
        setKbUsage(kb);
        setQuality(qual);

        const last7 = (daily.messages_daily || []).slice(-7);
        const w: WeeklyRow[] = last7.map((r) => ({
          day: arabicWeekday(r.day),
          استفسارات: r.messages,
        }));
        if (w.length) setWeeklyData(w);

        const pie: PieRow[] = (intents.top_intents || []).map((x) => ({
          name: x.intent || "unknown",
          value: x.total || 0,
        }));
        if (pie.length) setCategoryData(pie);

        const ts: WeeklyRow[] = (peak.hours || []).map((h) => ({
          day: `${h.hour}:00`,
          استفسارات: h.total,
        }));
        setTimeSeriesData(ts);
      })
      .catch((e: any) => {
        if (!alive) return;
        setStatsError(e?.message || "Failed to load stats");
      })
      .finally(() => {
        if (!alive) return;
        setLoadingStats(false);
      });

    // complaintsSummary اختياري
    StatsAPI.complaintsSummary(30, token)
      .then((complaints) => {
        if (!alive) return;

        setComplaintsTotal(complaints.total_complaints || 0);
        setComplaintsTable((complaints.breakdown || []) as any);

        const cpie: PieRow[] = (complaints.breakdown || [])
          .filter((x: any) => (x.total || 0) > 0)
          .map((x: any) => ({ name: x.category, value: x.total }));

        setComplaintsData(cpie.length ? cpie : [{ name: "لا توجد شكاوى", value: 0 }]);
      })
      .catch(() => {
        if (!alive) return;
        setComplaintsTotal(0);
        setComplaintsTable([]);
        setComplaintsData([{ name: "لا توجد شكاوى", value: 0 }]);
      });

    return () => {
      alive = false;
    };
  }, [token]);

  const statsCards = useMemo(() => {
    const lastDay = weeklyData?.[weeklyData.length - 1]?.استفسارات ?? 0;
    const totalToday = lastDay.toLocaleString("ar-PS");
    const autoRate = `${Math.round((overview?.answer_found_rate ?? 0) * 100)}%`;
    const conf = `${Math.round((overview?.avg_intent_conf ?? 0) * 100)}%`;

    const lowRated = (lowRatedConversations || []).length;
    const lowRatedLabel = lowRated.toLocaleString("ar-PS");

    return [
      { label: "إجمالي الاستفسارات (آخر يوم)", value: totalToday, icon: MessageSquare, color: "blue" as const },
      { label: "متوسط ثقة التصنيف", value: conf, icon: CheckCircle, color: "purple" as const },
      { label: "نسبة الإجابة التلقائية", value: autoRate, icon: CheckCircle, color: "green" as const },
      { label: "محادثات بتقييم منخفض (≤ 2 نجمة)", value: lowRatedLabel, icon: TrendingUp, color: "orange" as const },
    ];
  }, [overview, weeklyData, lowRatedConversations]);

  const topComplaint = useMemo(() => {
    const top = (complaintsTable || []).find((x) => (x.total || 0) > 0);
    if (!top) return null;
    return top;
  }, [complaintsTable]);

  const cardIconBg = (color: "blue" | "purple" | "green" | "orange") => {
    switch (color) {
      case "blue":
        return "bg-blue-100 text-blue-600";
      case "purple":
        return "bg-purple-100 text-purple-600";
      case "green":
        return "bg-green-100 text-green-600";
      case "orange":
        return "bg-orange-100 text-orange-600";
    }
  };

  // ✅ Export handlers
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

  return (
    <div className="flex h-screen bg-gray-50" dir="rtl">
      {/* Sidebar */}
      <div className="w-64 bg-gradient-to-b from-blue-600 to-blue-800 text-white p-6 relative">
        <div className="mb-8">
          <h2 className="text-xl font-bold">لوحة الموظف</h2>
          <p className="text-sm text-blue-200">كهرباء الخليل</p>
        </div>

        <nav className="space-y-2">
          <button
            onClick={() => setActiveTab("overview")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "overview" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <LayoutDashboard className="w-5 h-5" />
            <span>لوحة المعلومات</span>
          </button>

          <button
            onClick={() => setActiveTab("responses")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "responses" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <MessageSquare className="w-5 h-5" />
            <span>إدارة الردود</span>
          </button>

          {canViewReports && (
            <button
              onClick={() => setActiveTab("reports")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                activeTab === "reports" ? "bg-white/20" : "hover:bg-white/10"
              }`}
            >
              <BarChart3 className="w-5 h-5" />
              <span>التقارير</span>
            </button>
          )}

          {canViewReports && (
            <button
              onClick={() => setActiveTab("ratings")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                activeTab === "ratings" ? "bg-white/20" : "hover:bg-white/10"
              }`}
            >
              <Star className="w-5 h-5" />
              <span>التقييمات</span>
            </button>
          )}

          <button
            onClick={() => setActiveTab("files")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "files" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <Upload className="w-5 h-5" />
            <span>إدارة الملفات</span>
          </button>

          <button
            onClick={() => setActiveTab("unanswered")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
              activeTab === "unanswered" ? "bg-white/20" : "hover:bg-white/10"
            }`}
          >
            <HelpCircle className="w-5 h-5" />
            <span>الأسئلة غير المجابة</span>
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

      {/* Main */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">
              {activeTab === "overview" && "لوحة المعلومات"}
              {activeTab === "responses" && "إدارة الردود الذكية"}
              {activeTab === "reports" && "التقارير والإحصائيات"}
              {activeTab === "ratings" && "التقييمات"}
              {activeTab === "files" && "إدارة الملفات"}
              {activeTab === "unanswered" && "الأسئلة غير المجابة"}
            </h1>
            <p className="text-gray-600">
              {activeTab === "overview" && "نظرة عامة على أداء النظام"}
              {activeTab === "responses" && "إضافة وتعديل الردود في قاعدة المعرفة"}
              {activeTab === "reports" && "مراقبة الأداء وتحليل البيانات"}
              {activeTab === "ratings" && "تحليلات تقييم المحادثات (نجوم فقط)"}
              {activeTab === "files" && "رفع ملفات لإضافتها لقاعدة المعرفة بعد موافقة الإدارة"}
              {activeTab === "unanswered" && "الأسئلة التي لم يستطع الذكاء الاصطناعي الإجابة عليها"}
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
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {statsCards.map((stat, idx) => (
                  <div key={idx} className="bg-white rounded-xl shadow-md p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${cardIconBg(stat.color)}`}>
                        <stat.icon className="w-6 h-6" />
                      </div>
                    </div>
                    <h3 className="text-gray-600 text-sm mb-1">{stat.label}</h3>
                    <p className="text-3xl font-bold text-gray-800">{stat.value}</p>
                  </div>
                ))}
              </div>

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
                  <ResponsiveContainer width="100%" height={320}>
                    <PieChart>
                      <Pie
                        data={categoryData}
                        cx="50%" cy="45%"
                        outerRadius={110}
                        innerRadius={50}
                        dataKey="value"
                        label={false}
                      >
                        {categoryData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value: any, name: any) => [value, name]} />
                      <Legend
                        layout="horizontal"
                        verticalAlign="bottom"
                        align="center"
                        formatter={(value) => (
                          <span style={{ fontSize: "11px", color: "#374151" }}>
                            {value.length > 20 ? value.slice(0, 20) + "…" : value}
                          </span>
                        )}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* Responses */}
          {activeTab === "responses" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  {syncMsg && (
                    <span className={`text-sm font-medium px-3 py-1 rounded-lg ${syncMsg.startsWith("✅") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                      {syncMsg}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={syncKBToRAG}
                    disabled={syncingRAG}
                    title="مزامنة الردود مع الذكاء الاصطناعي"
                    className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white px-4 py-3 rounded-lg flex items-center gap-2 font-semibold transition-colors text-sm"
                  >
                    <RefreshCw className={`w-4 h-4 ${syncingRAG ? "animate-spin" : ""}`} />
                    {syncingRAG ? "جاري المزامنة..." : "مزامنة مع الذكاء الاصطناعي"}
                  </button>
                  <button
                    onClick={startAddNew}
                    disabled={isAddingNew || editingId !== null}
                    className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg flex items-center gap-2 font-semibold transition-colors"
                  >
                    <Plus className="w-5 h-5" />
                    إضافة رد جديد
                  </button>
                </div>
              </div>

              {(loadingKB || kbError) && (
                <div className="text-sm">
                  {loadingKB ? <span className="text-gray-500">تحميل الردود…</span> : null}
                  {kbError ? <span className="text-red-600">خطأ: {kbError}</span> : null}
                </div>
              )}

              {isAddingNew && (
                <div className="bg-white rounded-xl shadow-md p-6 text-gray-800">
                  <h3 className="text-xl font-bold mb-4">إضافة رد جديد</h3>

                  <div className="space-y-4">
                    <div>
                      <label className="block font-semibold mb-2">التصنيف</label>
                      <select
                        value={editForm.category}
                        onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3"
                      >
                        <option>استفسارات عامة</option>
                        <option>الفواتير</option>
                        <option>شكاوى</option>
                        <option>الاشتراكات</option>
                        <option>الدعم الفني</option>
                      </select>
                    </div>

                    <div>
                      <label className="block font-semibold mb-2">السؤال</label>
                      <input
                        type="text"
                        value={editForm.question}
                        onChange={(e) => setEditForm({ ...editForm, question: e.target.value })}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3"
                        placeholder="أدخل السؤال"
                      />
                    </div>

                    <div>
                      <label className="block font-semibold mb-2">الإجابة</label>
                      <textarea
                        value={editForm.answer}
                        onChange={(e) => setEditForm({ ...editForm, answer: e.target.value })}
                        rows={4}
                        className="w-full border border-gray-300 rounded-lg px-4 py-3"
                        placeholder="أدخل الإجابة"
                      />
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        id="active"
                        type="checkbox"
                        checked={editForm.is_active}
                        onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                      />
                      <label htmlFor="active" className="text-sm">
                        فعال
                      </label>
                    </div>

                    <div className="flex gap-3">
                      <button
                        onClick={saveKB}
                        className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg flex items-center gap-2 font-semibold"
                      >
                        <Save className="w-5 h-5" />
                        حفظ
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-6 py-2 rounded-lg flex items-center gap-2 font-semibold"
                      >
                        <X className="w-5 h-5" />
                        إلغاء
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <div className="space-y-4">
                {knowledgeItems.map((item) => (
                  <div key={item.id} className="bg-white rounded-xl shadow-md p-6 text-gray-800">
                    {editingId === item.id ? (
                      <div className="space-y-4">
                        <div>
                          <label className="block font-semibold mb-2">التصنيف</label>
                          <select
                            value={editForm.category}
                            onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                            className="w-full border border-gray-300 rounded-lg px-4 py-3"
                          >
                            <option>استفسارات عامة</option>
                            <option>الفواتير</option>
                            <option>شكاوى</option>
                            <option>الاشتراكات</option>
                            <option>الدعم الفني</option>
                          </select>
                        </div>

                        <div>
                          <label className="block font-semibold mb-2">السؤال</label>
                          <input
                            type="text"
                            value={editForm.question}
                            onChange={(e) => setEditForm({ ...editForm, question: e.target.value })}
                            className="w-full border border-gray-300 rounded-lg px-4 py-3"
                          />
                        </div>

                        <div>
                          <label className="block font-semibold mb-2">الإجابة</label>
                          <textarea
                            value={editForm.answer}
                            onChange={(e) => setEditForm({ ...editForm, answer: e.target.value })}
                            rows={4}
                            className="w-full border border-gray-300 rounded-lg px-4 py-3"
                          />
                        </div>

                        <div className="flex items-center gap-2">
                          <input
                            id={`active-${item.id}`}
                            type="checkbox"
                            checked={editForm.is_active}
                            onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                          />
                          <label htmlFor={`active-${item.id}`} className="text-sm">
                            فعال
                          </label>
                        </div>

                        <div className="flex gap-3">
                          <button
                            onClick={saveKB}
                            className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg flex items-center gap-2 font-semibold"
                          >
                            <Save className="w-5 h-5" />
                            حفظ
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-6 py-2 rounded-lg flex items-center gap-2 font-semibold"
                          >
                            <X className="w-5 h-5" />
                            إلغاء
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <span className="inline-block bg-blue-100 text-blue-700 text-xs font-semibold px-3 py-1 rounded-full mb-2">
                            {item.category}
                          </span>

                          {!item.is_active && (
                            <span className="inline-block bg-gray-100 text-gray-700 text-xs font-semibold px-3 py-1 rounded-full mb-2 mr-2">
                              غير فعال
                            </span>
                          )}

                          <h4 className="text-lg font-bold mb-2">{item.question}</h4>
                          <p className="text-gray-500 text-sm mt-1 overflow-hidden" style={{display:"-webkit-box",WebkitLineClamp:2,WebkitBoxOrient:"vertical",overflow:"hidden"}}>{item.answer}</p>

                          <p className="text-xs text-gray-400 mt-2">آخر تحديث: {item.updatedAt.toLocaleDateString("ar-PS")}</p>
                        </div>

                        <div className="flex gap-2">
                          <button
                            onClick={() => startEdit(item)}
                            disabled={editingId !== null || isAddingNew}
                            className="p-2 hover:bg-blue-50 text-blue-600 rounded-lg transition-colors disabled:opacity-50"
                          >
                            <Edit className="w-5 h-5" />
                          </button>
                          {canDelete && (
                            <button
                              onClick={() => removeKB(item.id)}
                              disabled={editingId !== null || isAddingNew}
                              className="p-2 hover:bg-red-50 text-red-600 rounded-lg transition-colors disabled:opacity-50"
                            >
                              <Trash2 className="w-5 h-5" />
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reports */}
          {activeTab === "reports" && (
            <div className="space-y-6">

              {/* بطاقات الملخص */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-xl p-5">
                  <p className="text-blue-100 text-xs mb-1">إجمالي الاستفسارات (شهر)</p>
                  <p className="text-3xl font-bold">{(overview?.total_messages ?? 0).toLocaleString("ar-PS")}</p>
                </div>
                <div className="bg-gradient-to-br from-green-500 to-green-600 text-white rounded-xl p-5">
                  <p className="text-green-100 text-xs mb-1">نسبة الإجابة التلقائية</p>
                  <p className="text-3xl font-bold">{Math.round((overview?.answer_found_rate ?? 0) * 100)}%</p>
                </div>
                <div className="bg-gradient-to-br from-red-500 to-red-600 text-white rounded-xl p-5">
                  <p className="text-red-100 text-xs mb-1">إجمالي الشكاوى (30 يوم)</p>
                  <p className="text-3xl font-bold">{complaintsTotal.toLocaleString("ar-PS")}</p>
                </div>
                <div className="bg-gradient-to-br from-purple-500 to-purple-600 text-white rounded-xl p-5">
                  <p className="text-purple-100 text-xs mb-1">أكثر شكوى</p>
                  <p className="text-lg font-bold truncate">{topComplaint?.category || "—"}</p>
                  <p className="text-xs text-purple-200">{topComplaint ? `${topComplaint.total} (${topComplaint.percent}%)` : ""}</p>
                </div>
              </div>

              {/* رسمان جنب بعض */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">الاستفسارات حسب الوقت</h3>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={timeSeriesData.length ? timeSeriesData : weeklyData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Line type="monotone" dataKey="استفسارات" stroke="#3B82F6" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">توزيع الشكاوى</h3>
                  {complaintsData.length > 0 && complaintsData[0].name !== "لا توجد شكاوى" ? (
                    <ResponsiveContainer width="100%" height={280}>
                      <PieChart>
                        <Pie
                          data={complaintsData}
                          cx="50%" cy="45%"
                          outerRadius={95}
                          innerRadius={40}
                          dataKey="value"
                          label={false}
                        >
                          {complaintsData.map((_, index) => (
                            <Cell key={index} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(value: any, name: any) => [value, name]} />
                        <Legend
                          layout="horizontal"
                          verticalAlign="bottom"
                          align="center"
                          formatter={(value) => (
                            <span style={{ fontSize: "11px", color: "#374151" }}>
                              {value.length > 18 ? value.slice(0, 18) + "…" : value}
                            </span>
                          )}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-64 flex items-center justify-center text-gray-400">لا توجد شكاوى 👍</div>
                  )}
                </div>
              </div>

              {/* جدول تفصيلي للشكاوى */}
              {complaintsTable.length > 0 && (
                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">تفاصيل الشكاوى</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-right text-gray-500 border-b">
                          <th className="pb-2">التصنيف</th>
                          <th className="pb-2">العدد</th>
                          <th className="pb-2">النسبة</th>
                          <th className="pb-2">التمثيل</th>
                        </tr>
                      </thead>
                      <tbody>
                        {complaintsTable.map((row, idx) => (
                          <tr key={idx} className="border-b last:border-0">
                            <td className="py-2 font-medium text-gray-800">{row.category}</td>
                            <td className="py-2 text-gray-600">{row.total}</td>
                            <td className="py-2 text-gray-600">{row.percent}%</td>
                            <td className="py-2 w-32">
                              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                <div className="h-full bg-blue-500 rounded-full" style={{ width: `${row.percent}%` }} />
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* ✅ أوضاع الردود */}
              {responseModes?.response_modes?.length ? (
                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">أوضاع الردود (Response Modes)</h3>
                  <div className="space-y-2">
                    {responseModes.response_modes.map((m) => {
                      const total = responseModes.response_modes.reduce((s, x) => s + x.total, 0);
                      const pct = total ? Math.round((m.total / total) * 100) : 0;
                      return (
                        <div key={m.mode} className="flex items-center gap-3">
                          <span className="w-36 text-sm text-gray-600 text-right">{m.mode}</span>
                          <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                            <div className="bg-blue-500 h-3 rounded-full" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="w-24 text-sm font-semibold text-gray-700 text-left">{m.total.toLocaleString("ar-PS")} ({pct}%)</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {/* ✅ جودة الردود */}
              {quality && (
                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">جودة الردود</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
                        <span className="text-sm text-gray-600">نسبة العثور على إجابة</span>
                        <span className="text-2xl font-bold text-green-700">
                          {(quality.answer_found_rate * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                        <span className="text-sm text-gray-600">متوسط أفضل تطابق</span>
                        <span className="text-2xl font-bold text-blue-700">
                          {quality.avg_best_score.toFixed(2)}
                        </span>
                      </div>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-700 mb-2">توزيع درجات التطابق</p>
                      <div className="space-y-1">
                        {quality.best_score_buckets.map((b) => (
                          <div key={b.bucket} className="flex items-center gap-2 text-sm">
                            <span className="w-16 text-gray-500">{b.bucket}</span>
                            <span className="font-semibold text-gray-800">{b.total.toLocaleString("ar-PS")} رسالة</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ✅ أكثر ملفات KB استخداماً */}
              {kbUsage?.kb_usage?.length ? (
                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">أكثر ملفات قاعدة المعرفة استخداماً</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-right text-gray-500 border-b">
                          <th className="pb-2">#</th>
                          <th className="pb-2">الملف / المصدر</th>
                          <th className="pb-2">عدد الاستخدامات</th>
                        </tr>
                      </thead>
                      <tbody>
                        {kbUsage.kb_usage.map((k, idx) => (
                          <tr key={k.source_file} className="border-b last:border-0 hover:bg-gray-50">
                            <td className="py-2 text-gray-400">{idx + 1}</td>
                            <td className="py-2 font-medium text-gray-800">{k.source_file}</td>
                            <td className="py-2 text-blue-700 font-semibold">{k.total.toLocaleString("ar-PS")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              {/* التصدير */}
              <div className="bg-white rounded-xl shadow-md p-6">
                <h3 className="text-lg font-bold text-gray-800 mb-1">تصدير التقرير</h3>
                <p className="text-sm text-gray-500 mb-4">تقرير شامل لآخر 30 يوم</p>
                <div className="flex flex-col sm:flex-row gap-3">
                  <button onClick={exportMonthlyExcel}
                    className="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg flex items-center justify-center gap-2 font-semibold">
                    <Download className="w-5 h-5" />تصدير Excel
                  </button>
                  <button onClick={exportMonthlyPDF}
                    className="bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-lg flex items-center justify-center gap-2 font-semibold">
                    <Download className="w-5 h-5" />تصدير PDF
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Ratings */}
          {activeTab === "ratings" && (
            <div className="space-y-6">
              <div className="bg-white rounded-xl shadow-md p-6">
                <h3 className="text-xl font-bold text-gray-800 mb-4">تحليلات تقييم المحادثة (نجوم)</h3>
                <RatingsAnalytics token={token} days={30} showDetails />
              </div>

              <div className="bg-white rounded-xl shadow-md p-6">
                <h3 className="text-xl font-bold text-gray-800 mb-2">مراجعة المحادثات قليلة التقييم (نجمة/نجمتين)</h3>
                <p className="text-sm text-gray-500 mb-4">بنركز فقط على المحادثات اللي تقييمها منخفض.</p>

                {lowRatedConversations.length === 0 ? (
                  <p className="text-gray-500">لا توجد محادثات بتقييم منخفض ضمن الفترة 👍</p>
                ) : (
                  <div className="space-y-3">
                    {lowRatedConversations.map((c) => (
                      <details key={c.conversation_id} className="border rounded-lg p-4">
                        <summary className="cursor-pointer flex flex-wrap items-center gap-3">
                          <span className="font-semibold text-gray-800">محادثة #{c.conversation_id}</span>
                          <span className="text-sm bg-yellow-50 text-yellow-800 border border-yellow-200 px-2 py-1 rounded">
                            ⭐ {c.avg_stars} / 5
                          </span>
                          <span className="text-sm text-gray-500">({c.ratings_count} تقييم)</span>
                          <span className="text-sm text-gray-500">
                            آخر تقييم: {new Date(c.last_rated_at).toLocaleDateString("ar-PS")}
                          </span>
                        </summary>

                        <div className="mt-3 space-y-2">
                          {(c.preview || []).map((m, i) => (
                            <div key={i} className="bg-gray-50 rounded p-3 text-sm">
                              <div className="text-xs text-gray-500 mb-1">{new Date(m.created_at).toLocaleString("ar-PS")}</div>
                              {m.message_text && (
                                <div className="mb-1">
                                  <span className="font-semibold">سؤال:</span> {m.message_text}
                                </div>
                              )}
                              {m.response_text && (
                                <div>
                                  <span className="font-semibold">رد:</span> {m.response_text}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </details>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* إدارة الملفات */}
          {activeTab === "files" && <FileManagement />}

          {/* الأسئلة غير المجابة */}
          {activeTab === "unanswered" && <UnansweredQuestions />}

        </div>
      </div>
    </div>
  );
}