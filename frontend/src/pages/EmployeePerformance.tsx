import { useState, useEffect, useCallback } from "react";
import {
  TrendingUp, Award, Clock, MessageSquare,
  CheckCircle, Star, Calendar, Users, RefreshCw,
  BookOpen, Pencil, Trash2, AlertCircle,
} from "lucide-react";
import {
  BarChart, Bar, LineChart, Line, RadarChart,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { StatsAPI, type EmployeesActivityResp, type EmployeeReportResp } from "../api/stats";
import { useAuth } from "../context/AuthContext";

interface EmployeePerformanceProps {
  selectedEmployeeId?: number | null;
}

const ROLE_LABEL: Record<string, string> = {
  employee:   "موظف دعم فني",
  supervisor: "مشرف",
  admin:      "مدير",
};

const STATUS_COLOR: Record<string, string> = {
  "نشط":             "bg-green-100 text-green-700",
  "قليل النشاط":    "bg-yellow-100 text-yellow-700",
  "غير مستخدم":     "bg-gray-100 text-gray-500",
};

export function EmployeePerformance({ selectedEmployeeId }: EmployeePerformanceProps) {
  const { token } = useAuth();

  const [days,     setDays]     = useState<30 | 7 | 365>(30);
  const [activity, setActivity] = useState<EmployeesActivityResp | null>(null);
  const [report,   setReport]   = useState<EmployeeReportResp | null>(null);
  const [selId,    setSelId]    = useState<number | null>(selectedEmployeeId ?? null);
  const [loading,  setLoading]  = useState(false);
  const [repLoading, setRepLoading] = useState(false);
  const [err,      setErr]      = useState("");

  // ── تحميل قائمة الموظفين ───────────────────────────────
  const loadActivity = useCallback(() => {
    if (!token) return;
    let alive = true;
    setLoading(true); setErr("");
    StatsAPI.employeesActivity(days, token)
      .then((d) => { if (alive) setActivity(d); })
      .catch((e: any) => { if (alive) setErr(e?.message || "فشل تحميل بيانات الموظفين"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [token, days]);

  useEffect(loadActivity, [loadActivity]);

  // ── تحميل تقرير موظف محدد ──────────────────────────────
  const loadReport = useCallback((userId: number) => {
    if (!token) return;
    let alive = true;
    setRepLoading(true);
    StatsAPI.employeeReport(userId, days, token)
      .then((r) => { if (alive) setReport(r); })
      .catch(() => { if (alive) setReport(null); })
      .finally(() => { if (alive) setRepLoading(false); });
    return () => { alive = false; };
  }, [token, days]);

  useEffect(() => {
    if (selId) loadReport(selId);
    else setReport(null);
  }, [selId, loadReport]);

  // ── إحصائيات مجمّعة ───────────────────────────────────
  const employees   = activity?.employees ?? [];
  const totalEmps   = employees.length;
  const activeEmps  = employees.filter((e) => e.status === "نشط").length;
  const totalLogins = employees.reduce((s, e) => s + e.logins, 0);
  const topEmp      = [...employees].sort((a, b) => b.active_minutes - a.active_minutes)[0];

  // بيانات المقارنة
  const comparisonData = employees.slice(0, 8).map((e) => ({
    name:     (e.name || "—").split(" ")[0],
    دقائق:    e.active_minutes,
    تسجيلات:  e.logins,
  }));

  // بيانات الـ radar للموظف المحدد
  const selEmp = employees.find((e) => e.user_id === selId);
  const maxMin  = Math.max(...employees.map((e) => e.active_minutes), 1);
  const maxLog  = Math.max(...employees.map((e) => e.logins), 1);
  const skillsData = report ? [
    { skill: "وقت النشاط",     value: Math.round((selEmp?.active_minutes ?? 0) / maxMin * 100) },
    { skill: "تسجيلات الدخول", value: Math.round((selEmp?.logins ?? 0) / maxLog * 100) },
    { skill: "إجابة الأسئلة",  value: Math.min(report.unanswered_answered * 5, 100) },
    { skill: "إضافة معرفة",    value: Math.min((report.kb_contributions.added) * 10, 100) },
    { skill: "تحديث المحتوى",  value: Math.min((report.kb_contributions.updated) * 5, 100) },
  ] : [];

  const fmtMin = (m: number) => {
    if (m < 60) return `${m} د`;
    return `${Math.floor(m / 60)}س ${m % 60}د`;
  };
  const fmtDate = (d: string | null) =>
    d ? new Date(d).toLocaleDateString("ar-PS", { month: "short", day: "numeric", year: "numeric" }) : "—";

  return (
    <div className="space-y-6" dir="rtl">

      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">تقارير أداء الموظفين</h2>
          <p className="text-gray-500 text-sm">بيانات حية من الباكند — البيانات من قاعدة بيانات النظام</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={days} onChange={(e) => setDays(Number(e.target.value) as 30|7|365)}
            className="border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500">
            <option value={7}>آخر 7 أيام</option>
            <option value={30}>آخر 30 يوم</option>
            <option value={365}>آخر سنة</option>
          </select>
          <button onClick={loadActivity} disabled={loading}
            className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> تحديث
          </button>
        </div>
      </div>

      {err && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
          <AlertCircle className="w-5 h-5 flex-shrink-0" /><span>{err}</span>
        </div>
      )}

      {/* بطاقات ملخص */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2"><Users className="w-8 h-8" /><span className="text-3xl font-bold">{totalEmps}</span></div>
          <h3 className="text-blue-100 text-sm">إجمالي الموظفين</h3>
          <p className="text-xs text-blue-200 mt-1">{activeEmps} نشط</p>
        </div>
        <div className="bg-gradient-to-br from-green-500 to-green-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2"><Clock className="w-8 h-8" /><span className="text-3xl font-bold">{totalEmps > 0 ? fmtMin(Math.round(employees.reduce((s,e)=>s+e.active_minutes,0)/totalEmps)) : "—"}</span></div>
          <h3 className="text-green-100 text-sm">متوسط وقت النشاط</h3>
          <p className="text-xs text-green-200 mt-1">آخر {days} يوم</p>
        </div>
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2"><Award className="w-8 h-8" /><span className="text-xl font-bold">{topEmp ? topEmp.name.split(" ")[0] : "—"}</span></div>
          <h3 className="text-purple-100 text-sm">الأكثر نشاطاً</h3>
          <p className="text-xs text-purple-200 mt-1">{topEmp ? fmtMin(topEmp.active_minutes) : ""}</p>
        </div>
        <div className="bg-gradient-to-br from-orange-500 to-orange-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2"><MessageSquare className="w-8 h-8" /><span className="text-3xl font-bold">{totalLogins}</span></div>
          <h3 className="text-orange-100 text-sm">إجمالي تسجيلات الدخول</h3>
          <p className="text-xs text-orange-200 mt-1">آخر {days} يوم</p>
        </div>
      </div>

      {/* بطاقات الموظفين */}
      {loading ? (
        <div className="flex items-center justify-center py-16 gap-3 text-gray-500">
          <RefreshCw className="w-5 h-5 animate-spin" /><span>تحميل بيانات الموظفين…</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {employees.map((emp) => (
            <div key={emp.user_id} onClick={() => setSelId(emp.user_id === selId ? null : emp.user_id)}
              className={`bg-white rounded-xl shadow-md p-6 cursor-pointer transition-all hover:shadow-xl ${
                selId === emp.user_id ? "ring-2 ring-purple-500" : ""
              }`}>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-blue-500 rounded-full flex items-center justify-center text-white font-bold text-lg">
                    {(emp.name || "؟").charAt(0)}
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-800">{emp.name || "—"}</h3>
                    <p className="text-xs text-gray-500">{ROLE_LABEL[emp.role] || emp.role}</p>
                  </div>
                </div>
                <span className={`text-xs font-semibold px-2 py-1 rounded-full ${STATUS_COLOR[emp.status] || "bg-gray-100 text-gray-500"}`}>
                  {emp.status}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">وقت النشاط</p>
                  <p className="text-lg font-bold text-gray-800">{fmtMin(emp.active_minutes)}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">تسجيلات الدخول</p>
                  <p className="text-lg font-bold text-gray-800">{emp.logins}</p>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-3">
                آخر نشاط: {fmtDate(emp.last_activity)}
              </p>
            </div>
          ))}
          {employees.length === 0 && !loading && (
            <div className="col-span-3 text-center py-12 text-gray-400">
              <Users className="w-12 h-12 mx-auto mb-3 text-gray-200" />
              <p>لا توجد بيانات موظفين</p>
            </div>
          )}
        </div>
      )}

      {/* تفاصيل الموظف المحدد */}
      {selId && (
        <div className="space-y-6">
          <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-xl p-6 flex items-center justify-between">
            <div>
              <h3 className="text-xl font-bold text-gray-800">
                تفاصيل أداء: {selEmp?.name || "..."}
              </h3>
              <p className="text-gray-500 text-sm">{ROLE_LABEL[selEmp?.role || ""] || selEmp?.role}</p>
            </div>
            {repLoading && <RefreshCw className="w-5 h-5 text-purple-400 animate-spin" />}
          </div>

          {report && (
            <>
              {/* إحصائيات تفصيلية */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="bg-white rounded-xl shadow-md p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                      <Clock className="w-5 h-5 text-blue-600" />
                    </div>
                    <div>
                      <h4 className="font-bold text-gray-800 text-sm">وقت النشاط</h4>
                      <p className="text-xs text-gray-500">آخر {days} يوم</p>
                    </div>
                  </div>
                  <p className="text-3xl font-bold text-blue-600">{fmtMin(report.sessions.total_minutes)}</p>
                  <p className="text-sm text-gray-500 mt-1">{report.sessions.logins} تسجيل دخول</p>
                </div>

                <div className="bg-white rounded-xl shadow-md p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    </div>
                    <div>
                      <h4 className="font-bold text-gray-800 text-sm">أسئلة المواطنين</h4>
                      <p className="text-xs text-gray-500">تم الرد عليها</p>
                    </div>
                  </div>
                  <p className="text-3xl font-bold text-green-600">{report.unanswered_answered}</p>
                  <p className="text-sm text-gray-500 mt-1">إجابة مباشرة</p>
                </div>

                <div className="bg-white rounded-xl shadow-md p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                      <BookOpen className="w-5 h-5 text-purple-600" />
                    </div>
                    <div>
                      <h4 className="font-bold text-gray-800 text-sm">إضافة للمعرفة</h4>
                      <p className="text-xs text-gray-500">مقالات جديدة</p>
                    </div>
                  </div>
                  <p className="text-3xl font-bold text-purple-600">{report.kb_contributions.added}</p>
                  <p className="text-sm text-gray-500 mt-1">من {report.kb_contributions.total} تغيير</p>
                </div>

                <div className="bg-white rounded-xl shadow-md p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                      <Pencil className="w-5 h-5 text-orange-600" />
                    </div>
                    <div>
                      <h4 className="font-bold text-gray-800 text-sm">تحديث المحتوى</h4>
                      <p className="text-xs text-gray-500">تعديلات</p>
                    </div>
                  </div>
                  <p className="text-3xl font-bold text-orange-600">{report.kb_contributions.updated}</p>
                  <p className="text-sm text-gray-500 mt-1">{report.kb_contributions.deleted} حذف</p>
                </div>
              </div>

              {/* الرسوم البيانية */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Radar */}
                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-xl font-bold text-gray-800 mb-4">تقييم المهارات</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <RadarChart data={skillsData}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="skill" />
                      <PolarRadiusAxis angle={90} domain={[0, 100]} />
                      <Radar name="الأداء" dataKey="value" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.5} />
                      <Tooltip />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                {/* آخر التغييرات */}
                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-xl font-bold text-gray-800 mb-4">آخر التغييرات على قاعدة المعرفة</h3>
                  {report.recent_kb_changes.length === 0 ? (
                    <div className="flex items-center justify-center h-48 text-gray-400 flex-col gap-2">
                      <BookOpen className="w-10 h-10 text-gray-200" />
                      <p>لا توجد تغييرات بعد</p>
                    </div>
                  ) : (
                    <div className="space-y-3 max-h-64 overflow-y-auto">
                      {report.recent_kb_changes.map((ch, i) => (
                        <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                          {ch.action === "create" && <BookOpen className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />}
                          {ch.action === "update" && <Pencil className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />}
                          {ch.action === "delete" && <Trash2 className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-gray-800 truncate">{ch.new_question || "—"}</p>
                            <p className="text-xs text-gray-400">{fmtDate(ch.changed_at)}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* معلومات الحساب */}
              <div className="bg-white rounded-xl shadow-md p-6">
                <h3 className="text-xl font-bold text-gray-800 mb-4">معلومات الحساب</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div><p className="text-gray-500 mb-1">اسم المستخدم</p><p className="font-semibold text-gray-800">{report.employee.username}</p></div>
                  <div><p className="text-gray-500 mb-1">الدور</p><p className="font-semibold text-gray-800">{ROLE_LABEL[report.employee.role] || report.employee.role}</p></div>
                  <div><p className="text-gray-500 mb-1">آخر دخول</p><p className="font-semibold text-gray-800">{fmtDate(report.employee.last_login)}</p></div>
                  <div><p className="text-gray-500 mb-1">الحالة</p>
                    <span className={`text-xs font-semibold px-2 py-1 rounded-full ${report.employee.status === "active" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                      {report.employee.status === "active" ? "نشط" : "معطّل"}
                    </span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* مقارنة الموظفين */}
      {comparisonData.length > 0 && (
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">مقارنة الأداء بين الموظفين</h3>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={comparisonData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="دقائق" fill="#8B5CF6" radius={[4,4,0,0]} />
              <Bar dataKey="تسجيلات" fill="#10B981" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}