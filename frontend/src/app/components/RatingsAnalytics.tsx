import { useEffect, useMemo, useState } from "react";
import { Star, TrendingUp, MessageSquare, Calendar, Filter } from "lucide-react";
import { BarChart, Bar, PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { RatingsAPI } from "../../api/ratings";
import { StatsAPI, ConvRatingsSummaryRangeResp, ConvRatingsDailyRangeResp, RecentRatingsRangeResp } from "../../api/stats";

type Props = { token: string; days?: number; showDetails?: boolean };

export function RatingsAnalytics({ token, days = 30, showDetails = false }: Props) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const [summary, setSummary] = useState<any>(null);
  const [daily, setDaily] = useState<any>(null);
  const [recent, setRecent] = useState<any>(null);

  // ✅ فلتر بالتاريخ - مربوط بالـ range endpoints الجديدة
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [rangeMode, setRangeMode] = useState(false);
  const [rangeSummary, setRangeSummary] = useState<ConvRatingsSummaryRangeResp | null>(null);
  const [rangeDaily, setRangeDaily] = useState<ConvRatingsDailyRangeResp | null>(null);
  const [rangeRecent, setRangeRecent] = useState<RecentRatingsRangeResp | null>(null);
  const [rangeLoading, setRangeLoading] = useState(false);
  const [rangeErr, setRangeErr] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr("");

    Promise.all([
      RatingsAPI.summary(days, token),
      RatingsAPI.daily(7, token),
      RatingsAPI.recent(5, days, token),
    ])
      .then(([s, d, r]) => {
        if (!alive) return;
        setSummary(s);
        setDaily(d);
        setRecent(r);
      })
      .catch((e: any) => {
        if (!alive) return;
        setErr(e?.message || "فشل تحميل التقييمات");
      })
      .finally(() => {
        if (!alive) return;
        setLoading(false);
      });

    return () => { alive = false; };
  }, [token, days]);

  const fetchRange = () => {
    if (!fromDate && !toDate) return;
    let alive = true;
    setRangeLoading(true);
    setRangeErr("");
    setRangeMode(true);

    Promise.all([
      StatsAPI.conversationRatingsSummaryRange(token, fromDate || undefined, toDate || undefined),
      StatsAPI.conversationRatingsDailyRange(token, fromDate || undefined, toDate || undefined),
      StatsAPI.recentRatingsRange(token, 50, fromDate || undefined, toDate || undefined),
    ])
      .then(([rs, rd, rr]) => {
        if (!alive) return;
        setRangeSummary(rs);
        setRangeDaily(rd);
        setRangeRecent(rr);
      })
      .catch((e: any) => {
        if (!alive) return;
        setRangeErr(e?.message || "فشل جلب البيانات");
      })
      .finally(() => {
        if (!alive) return;
        setRangeLoading(false);
      });

    return () => { alive = false; };
  };

  const clearRange = () => {
    setRangeMode(false);
    setFromDate("");
    setToDate("");
    setRangeSummary(null);
    setRangeDaily(null);
    setRangeRecent(null);
  };

  const stats = useMemo(() => {
    if (rangeMode && rangeSummary) {
      return {
        total: rangeSummary.total_ratings,
        avg: rangeSummary.avg_rating,
        sat: rangeSummary.satisfaction_rate,
      };
    }
    const total = summary?.total_ratings ?? 0;
    const avg = summary?.avg_stars ?? 0;
    const sat = summary?.satisfaction_rate ?? 0;
    return { total, avg, sat };
  }, [summary, rangeSummary, rangeMode]);

  const starDistribution = useMemo(() => {
    const colors: Record<number, string> = { 1: "#EF4444", 2: "#F97316", 3: "#EAB308", 4: "#84CC16", 5: "#22C55E" };
    const dist = rangeMode ? (rangeSummary?.star_distribution ?? []) : (summary?.distribution ?? []);
    return dist.map((x: any) => ({
      name: `${x.stars} نجمة`,
      value: x.total,
      color: colors[x.stars] || "#999",
    }));
  }, [summary, rangeSummary, rangeMode]);

  const weeklyData = useMemo(() => {
    if (rangeMode) {
      const rows = rangeDaily?.daily ?? [];
      return rows.map((r: any) => ({
        day: new Date(r.day).toLocaleDateString("ar-PS", { weekday: "short", month: "short", day: "numeric" }),
        متوسط: Number(r.avg_rating || 0),
        عدد: Number(r.total || 0),
      }));
    }
    const rows = daily?.by_day ?? [];
    return rows.map((r: any) => ({
      day: new Date(r.day).toLocaleDateString("ar-PS", { weekday: "short" }),
      متوسط: Number(r.avg_stars || 0),
      عدد: Number(r.count || 0),
    }));
  }, [daily, rangeDaily, rangeMode]);

  const recentFeedback = useMemo(() => {
    if (rangeMode) {
      return (rangeRecent?.items ?? []).filter((x: any) => (x.comment || "").trim());
    }
    const items = recent?.items ?? [];
    return items.filter((x: any) => (x.comment || "").trim());
  }, [recent, rangeRecent, rangeMode]);

  if (loading) return <div className="text-gray-500">تحميل التقييمات…</div>;
  if (err) return <div className="text-red-600">خطأ: {err}</div>;

  return (
    <div className="space-y-6" dir="rtl">

      {/* ✅ فلتر بالتاريخ - مربوط بـ range endpoints */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Filter className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-semibold text-gray-700">فلترة بالتاريخ:</span>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">من:</label>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">إلى:</label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <button
            onClick={fetchRange}
            disabled={rangeLoading || (!fromDate && !toDate)}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-4 py-1 rounded text-sm font-semibold"
          >
            {rangeLoading ? "جاري…" : "تطبيق"}
          </button>
          {rangeMode && (
            <button onClick={clearRange} className="text-sm text-gray-500 underline">
              مسح الفلتر
            </button>
          )}
        </div>
        {rangeMode && (
          <p className="text-xs text-blue-600 mt-2">
            عرض بيانات الفترة: {fromDate || "البداية"} → {toDate || "اليوم"}
          </p>
        )}
        {rangeErr && <p className="text-xs text-red-600 mt-1">{rangeErr}</p>}
      </div>

      {/* cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <Star className="w-8 h-8" />
            <span className="text-3xl font-bold">{Number(stats.avg).toFixed(1)}</span>
          </div>
          <h3 className="text-blue-100 text-sm">متوسط التقييم</h3>
          <p className="text-xs text-blue-200 mt-1">من {stats.total} تقييم</p>
        </div>

        <div className="bg-gradient-to-br from-green-500 to-green-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <TrendingUp className="w-8 h-8" />
            <span className="text-3xl font-bold">{stats.sat}%</span>
          </div>
          <h3 className="text-green-100 text-sm">نسبة الرضا</h3>
          <p className="text-xs text-green-200 mt-1">4-5 نجوم</p>
        </div>

        <div className="bg-gradient-to-br from-orange-500 to-orange-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <MessageSquare className="w-8 h-8" />
            <span className="text-3xl font-bold">{stats.total}</span>
          </div>
          <h3 className="text-orange-100 text-sm">إجمالي التقييمات</h3>
          <p className="text-xs text-orange-200 mt-1">{rangeMode ? "الفترة المحددة" : `آخر ${days} يوم`}</p>
        </div>
      </div>

      {/* charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">توزيع النجوم</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={starDistribution} cx="50%" cy="50%" outerRadius={100} dataKey="value" label={(e) => (e.value > 0 ? `${e.name}: ${e.value}` : "")}>
                {starDistribution.map((e: any, i: number) => (
                  <Cell key={i} fill={e.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">
            {rangeMode ? "متوسط التقييم حسب اليوم" : "متوسط التقييم آخر 7 أيام"}
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={weeklyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis domain={[0, 5]} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="متوسط" strokeWidth={2} stroke="#3B82F6" />
              <Bar dataKey="عدد" fill="#E5E7EB" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* recent feedback */}
      {showDetails && recentFeedback.length > 0 && (
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">
            آخر التعليقات {rangeMode ? "(الفترة المحددة)" : ""}
          </h3>
          <div className="space-y-3">
            {recentFeedback.map((x: any, idx: number) => (
              <div key={idx} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {[1,2,3,4,5].map((s) => (
                      <Star key={s} className={`w-4 h-4 ${s <= (x.stars || 0) ? "fill-yellow-400 text-yellow-400" : "text-gray-300"}`} />
                    ))}
                    <span className="text-sm font-semibold text-gray-700">{x.stars}/5</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <Calendar className="w-4 h-4" />
                    <span>{new Date(x.submitted_at).toLocaleDateString("ar-PS")}</span>
                  </div>
                </div>
                <p className="text-gray-700">{x.comment}</p>
                <p className="text-xs text-gray-500 mt-2">محادثة #{x.conversation_id}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}