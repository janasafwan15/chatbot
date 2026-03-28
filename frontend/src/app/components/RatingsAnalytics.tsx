import { useEffect, useMemo, useState } from "react";
import {
  Star, TrendingUp, MessageSquare, Calendar,
  Filter, ThumbsUp, ThumbsDown, RefreshCw,
} from "lucide-react";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { RatingsAPI } from "../../api/ratings";
import {
  StatsAPI,
  type ConvRatingsSummaryRangeResp,
  type ConvRatingsDailyRangeResp,
  type RecentRatingsRangeResp,
} from "../../api/stats";
import { apiFetch } from "../../api/http";

interface HelpfulStats {
  total_helpful:     number;
  total_not_helpful: number;
  positive_rate:     number;
}

async function fetchHelpfulStats(token: string, days: number): Promise<HelpfulStats> {
  return apiFetch<HelpfulStats>(`/stats/helpful-summary?days=${days}`, { token });
}

type Props = { token: string; days?: number; showDetails?: boolean };

const STAR_COLORS: Record<number, string> = {
  1: "#EF4444", 2: "#F97316", 3: "#EAB308", 4: "#84CC16", 5: "#22C55E",
};

export function RatingsAnalytics({ token, days = 30, showDetails = false }: Props) {
  const [loading,  setLoading]  = useState(false);
  const [err,      setErr]      = useState("");
  const [summary,  setSummary]  = useState<any>(null);
  const [daily,    setDaily]    = useState<any>(null);
  const [recent,   setRecent]   = useState<any>(null);
  const [helpful,  setHelpful]  = useState<HelpfulStats | null>(null);

  const [fromDate,     setFromDate]     = useState("");
  const [toDate,       setToDate]       = useState("");
  const [rangeMode,    setRangeMode]    = useState(false);
  const [rangeSummary, setRangeSummary] = useState<ConvRatingsSummaryRangeResp | null>(null);
  const [rangeDaily,   setRangeDaily]   = useState<ConvRatingsDailyRangeResp | null>(null);
  const [rangeRecent,  setRangeRecent]  = useState<RecentRatingsRangeResp | null>(null);
  const [rangeLoading, setRangeLoading] = useState(false);
  const [rangeErr,     setRangeErr]     = useState("");

  const load = () => {
    let alive = true;
    setLoading(true);
    setErr("");
    Promise.all([
      RatingsAPI.summary(days, token),
      RatingsAPI.daily(7, token),
      RatingsAPI.recent(5, days, token),
      fetchHelpfulStats(token, days).catch(() => null),
    ])
      .then(([s, d, r, h]) => {
        if (!alive) return;
        setSummary(s); setDaily(d); setRecent(r); setHelpful(h);
      })
      .catch((e: any) => { if (!alive) return; setErr(e?.message || "فشل تحميل التقييمات"); })
      .finally(() => { if (!alive) return; setLoading(false); });
    return () => { alive = false; };
  };

  useEffect(load, [token, days]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchRange = () => {
    if (!fromDate && !toDate) return;
    let alive = true;
    setRangeLoading(true); setRangeErr(""); setRangeMode(true);
    Promise.all([
      StatsAPI.conversationRatingsSummaryRange(token, fromDate || undefined, toDate || undefined),
      StatsAPI.conversationRatingsDailyRange(token, fromDate || undefined, toDate || undefined),
      StatsAPI.recentRatingsRange(token, 50, fromDate || undefined, toDate || undefined),
    ])
      .then(([rs, rd, rr]) => { if (!alive) return; setRangeSummary(rs); setRangeDaily(rd); setRangeRecent(rr); })
      .catch((e: any) => { if (!alive) return; setRangeErr(e?.message || "فشل جلب البيانات"); })
      .finally(() => { if (!alive) return; setRangeLoading(false); });
    return () => { alive = false; };
  };

  const clearRange = () => {
    setRangeMode(false); setFromDate(""); setToDate("");
    setRangeSummary(null); setRangeDaily(null); setRangeRecent(null);
  };

  const stats = useMemo(() => {
    if (rangeMode && rangeSummary)
      return { total: rangeSummary.total_ratings, avg: rangeSummary.avg_rating, sat: rangeSummary.satisfaction_rate };
    return { total: summary?.total_ratings ?? 0, avg: summary?.avg_stars ?? 0, sat: summary?.satisfaction_rate ?? 0 };
  }, [summary, rangeSummary, rangeMode]);

  const starDistribution = useMemo(() => {
    const dist = rangeMode ? (rangeSummary?.star_distribution ?? []) : (summary?.distribution ?? []);
    return dist.map((x: any) => ({ name: `${x.stars} ⭐`, value: x.total, color: STAR_COLORS[x.stars] || "#999" }));
  }, [summary, rangeSummary, rangeMode]);

  const weeklyData = useMemo(() => {
    if (rangeMode)
      return (rangeDaily?.daily ?? []).map((r: any) => ({
        day: new Date(r.day).toLocaleDateString("ar-PS", { weekday: "short", month: "short", day: "numeric" }),
        متوسط: Number(r.avg_rating || 0), عدد: Number(r.total || 0),
      }));
    return (daily?.by_day ?? []).map((r: any) => ({
      day: new Date(r.day).toLocaleDateString("ar-PS", { weekday: "short" }),
      متوسط: Number(r.avg_stars || 0), عدد: Number(r.count || 0),
    }));
  }, [daily, rangeDaily, rangeMode]);

  const recentFeedback = useMemo(() => {
    const items = rangeMode ? (rangeRecent?.items ?? []) : (recent?.items ?? []);
    return items.filter((x: any) => (x.comment || "").trim());
  }, [recent, rangeRecent, rangeMode]);

  const positiveCount   = helpful?.total_helpful     ?? 0;
  const negativeCount   = helpful?.total_not_helpful ?? 0;
  const positiveRate    = helpful?.positive_rate     ?? 0;
  const totalMsgRatings = positiveCount + negativeCount;

  if (loading) return (
    <div className="flex items-center justify-center py-16 gap-3 text-gray-500">
      <RefreshCw className="w-5 h-5 animate-spin" /><span>تحميل التقييمات…</span>
    </div>
  );
  if (err) return (
    <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
      <span>⚠️ {err}</span>
      <button onClick={load} className="underline text-sm">إعادة المحاولة</button>
    </div>
  );

  return (
    <div className="space-y-6" dir="rtl">

      {/* فلتر التاريخ */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Filter className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-semibold text-gray-700">فلترة بالتاريخ:</span>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">من:</label>
            <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1 text-sm" />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">إلى:</label>
            <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1 text-sm" />
          </div>
          <button onClick={fetchRange} disabled={rangeLoading || (!fromDate && !toDate)}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-4 py-1 rounded text-sm font-semibold">
            {rangeLoading ? "جاري…" : "تطبيق"}
          </button>
          {rangeMode && <button onClick={clearRange} className="text-sm text-gray-500 underline">مسح الفلتر</button>}
          <button onClick={load} title="تحديث" className="mr-auto p-1.5 rounded hover:bg-gray-200 transition-colors">
            <RefreshCw className="w-4 h-4 text-gray-500" />
          </button>
        </div>
        {rangeMode && <p className="text-xs text-blue-600 mt-2">عرض بيانات: {fromDate || "البداية"} → {toDate || "اليوم"}</p>}
        {rangeErr  && <p className="text-xs text-red-600 mt-1">{rangeErr}</p>}
      </div>

      {/* بطاقات الإحصائيات */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2"><Star className="w-8 h-8" /><span className="text-3xl font-bold">{Number(stats.avg).toFixed(1)}</span></div>
          <h3 className="text-blue-100 text-sm">متوسط التقييم</h3>
          <p className="text-xs text-blue-200 mt-1">من {stats.total} تقييم</p>
        </div>
        <div className="bg-gradient-to-br from-green-500 to-green-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2"><TrendingUp className="w-8 h-8" /><span className="text-3xl font-bold">{stats.sat}%</span></div>
          <h3 className="text-green-100 text-sm">نسبة الرضا</h3>
          <p className="text-xs text-green-200 mt-1">تقييم 4–5 نجوم</p>
        </div>
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2"><ThumbsUp className="w-8 h-8" /><span className="text-3xl font-bold">{totalMsgRatings > 0 ? `${Number(positiveRate).toFixed(1)}%` : "—"}</span></div>
          <h3 className="text-purple-100 text-sm">تقييمات إيجابية</h3>
          <p className="text-xs text-purple-200 mt-1">{positiveCount} من {totalMsgRatings} رسالة</p>
        </div>
        <div className="bg-gradient-to-br from-orange-500 to-orange-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2"><MessageSquare className="w-8 h-8" /><span className="text-3xl font-bold">{stats.total}</span></div>
          <h3 className="text-orange-100 text-sm">إجمالي التقييمات</h3>
          <p className="text-xs text-orange-200 mt-1">{rangeMode ? "الفترة المحددة" : `آخر ${days} يوم`}</p>
        </div>
      </div>

      {/* الرسوم البيانية */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">توزيع التقييمات</h3>
          {starDistribution.every((x: any) => x.value === 0) ? (
            <div className="flex items-center justify-center h-64 text-gray-400 flex-col gap-2">
              <Star className="w-12 h-12 text-gray-200" /><p>لا توجد تقييمات بعد</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={starDistribution} cx="50%" cy="50%" outerRadius={100} dataKey="value"
                  label={(e) => e.value > 0 ? `${e.name}: ${e.value}` : ""}>
                  {starDistribution.map((e: any, i: number) => <Cell key={i} fill={e.color} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">
            {rangeMode ? "متوسط التقييم حسب اليوم" : "متوسط التقييم آخر 7 أيام"}
          </h3>
          {weeklyData.length === 0 ? (
            <div className="flex items-center justify-center h-64 text-gray-400 flex-col gap-2">
              <Calendar className="w-12 h-12 text-gray-200" /><p>لا توجد بيانات</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={weeklyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" /><YAxis domain={[0, 5]} />
                <Tooltip /><Legend />
                <Line type="monotone" dataKey="متوسط" stroke="#3B82F6" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* تقييمات الرسائل */}
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">تقييمات الرسائل</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
              <div className="flex items-center gap-3"><ThumbsUp className="w-6 h-6 text-green-600" /><span className="font-semibold text-gray-800">إيجابي</span></div>
              <span className="text-2xl font-bold text-green-600">{positiveCount}</span>
            </div>
            <div className="flex items-center justify-between p-4 bg-red-50 rounded-lg">
              <div className="flex items-center gap-3"><ThumbsDown className="w-6 h-6 text-red-600" /><span className="font-semibold text-gray-800">سلبي</span></div>
              <span className="text-2xl font-bold text-red-600">{negativeCount}</span>
            </div>
            {totalMsgRatings > 0 ? (
              <div className="p-4 bg-blue-50 rounded-lg">
                <div className="flex justify-between mb-2">
                  <span className="text-sm text-gray-600">نسبة الإيجابية</span>
                  <span className="text-sm font-semibold text-blue-600">{Number(positiveRate).toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div className="bg-blue-500 h-3 rounded-full transition-all" style={{ width: `${positiveRate}%` }} />
                </div>
              </div>
            ) : (
              <p className="text-center text-sm text-gray-400 py-4">لا توجد تقييمات رسائل بعد</p>
            )}
          </div>
        </div>

        {/* عدد التقييمات اليومية */}
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">عدد التقييمات اليومية</h3>
          {weeklyData.length === 0 ? (
            <div className="flex items-center justify-center h-64 text-gray-400"><p>لا توجد بيانات</p></div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={weeklyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" /><YAxis allowDecimals={false} />
                <Tooltip /><Legend />
                <Bar dataKey="عدد" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* آخر التعليقات */}
      {showDetails && recentFeedback.length > 0 && (
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">آخر التعليقات {rangeMode ? "(الفترة المحددة)" : ""}</h3>
          <div className="space-y-3">
            {recentFeedback.map((x: any, idx: number) => (
              <div key={idx} className="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1">
                    {[1,2,3,4,5].map((s) => (
                      <Star key={s} className={`w-4 h-4 ${s <= (x.stars||0) ? "fill-yellow-400 text-yellow-400" : "text-gray-300"}`} />
                    ))}
                    <span className="text-sm font-semibold text-gray-700 mr-1">{x.stars}/5</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <Calendar className="w-4 h-4" />
                    <span>{new Date(x.submitted_at).toLocaleDateString("ar-PS")}</span>
                  </div>
                </div>
                <p className="text-gray-700 text-sm leading-relaxed">{x.comment}</p>
                <p className="text-xs text-gray-400 mt-2">محادثة #{x.conversation_id}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* لا توجد بيانات */}
      {stats.total === 0 && totalMsgRatings === 0 && (
        <div className="bg-white rounded-xl shadow-md p-12 text-center">
          <MessageSquare className="w-16 h-16 text-gray-200 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-gray-800 mb-2">لا توجد تقييمات بعد</h3>
          <p className="text-gray-500">سيتم عرض التقييمات والإحصائيات هنا بمجرد بدء المستخدمين بتقييم الخدمة</p>
        </div>
      )}
    </div>
  );
}