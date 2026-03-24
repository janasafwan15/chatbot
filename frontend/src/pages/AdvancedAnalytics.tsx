// frontend/src/pages/AdvancedAnalytics.tsx
import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import {
  Brain, MapPin, TrendingUp, Zap, RefreshCcw,
  AlertCircle, CheckCircle, Database, Clock, Activity,
} from "lucide-react";
import { AnalyticsAPI } from "../api/stats";

interface Props {
  token: string;
  role: string;
}

type Tab = "problems" | "neighborhoods" | "rag_metrics" | "llm_usage" | "admin";

export default function AdvancedAnalytics({ token, role }: Props) {
  const [tab, setTab] = useState<Tab>("problems");
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Data states
  const [problems, setProblems] = useState<any>(null);
  const [neighborhoods, setNeighborhoods] = useState<any>(null);
  const [ragMetrics, setRagMetrics] = useState<any>(null);
  const [llmUsage, setLlmUsage] = useState<any>(null);
  const [kbHealth, setKbHealth] = useState<any>(null);
  const [rebuildStatus, setRebuildStatus] = useState<any>(null);
  const [rebuildRunning, setRebuildRunning] = useState(false);

  const isAdmin = role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (tab === "problems") {
        const [p, n] = await Promise.all([
          AnalyticsAPI.chatProblems(days, token),
          AnalyticsAPI.neighborhoodComplaints(days, token),
        ]);
        setProblems(p);
        setNeighborhoods(n);
      } else if (tab === "neighborhoods") {
        const n = await AnalyticsAPI.neighborhoodComplaints(days, token);
        setNeighborhoods(n);
      } else if (tab === "rag_metrics") {
        const r = await AnalyticsAPI.ragEvalMetrics(days, token);
        setRagMetrics(r);
      } else if (tab === "llm_usage" && isAdmin) {
        const l = await AnalyticsAPI.llmUsage(days * 24, token);
        setLlmUsage(l);
      } else if (tab === "admin" && isAdmin) {
        const [k, s] = await Promise.all([
          AnalyticsAPI.kbHealth(token),
          AnalyticsAPI.rebuildEmbeddingsStatus(token),
        ]);
        setKbHealth(k);
        setRebuildStatus(s);
        setRebuildRunning(s?.running || false);
      }
    } catch (e: any) {
      setError(e.message || "خطأ في التحميل");
    } finally {
      setLoading(false);
    }
  }, [tab, days, token, isAdmin]);

  useEffect(() => { load(); }, [load]);

  // Poll rebuild status
  useEffect(() => {
    if (!rebuildRunning) return;
    const id = setInterval(async () => {
      try {
        const s = await AnalyticsAPI.rebuildEmbeddingsStatus(token);
        setRebuildStatus(s);
        if (!s.running) setRebuildRunning(false);
      } catch {}
    }, 2000);
    return () => clearInterval(id);
  }, [rebuildRunning, token]);

  const startRebuild = async (overwrite: boolean) => {
    try {
      await AnalyticsAPI.rebuildEmbeddings(overwrite, token);
      setRebuildRunning(true);
      setTimeout(load, 500);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const tabs: { id: Tab; label: string; icon: any; adminOnly?: boolean }[] = [
    { id: "problems",      label: "أكثر المشاكل",     icon: Brain },
    { id: "neighborhoods", label: "الأحياء الشاكية",  icon: MapPin },
    { id: "rag_metrics",   label: "جودة RAG",          icon: TrendingUp },
    { id: "llm_usage",     label: "استهلاك LLM",       icon: Zap, adminOnly: true },
    { id: "admin",         label: "Admin Controls",    icon: Database, adminOnly: true },
  ];

  return (
    <div style={{ padding: "24px", direction: "rtl", fontFamily: "system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: "#1e1b4b", margin: 0 }}>
          📊 تحليلات متقدمة
        </h1>
        <p style={{ color: "#6b7280", margin: "4px 0 0" }}>
          تحليل المحادثات • جودة الذكاء الاصطناعي • مراقبة النظام
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
        {tabs.filter(t => !t.adminOnly || isAdmin).map(t => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 16px", borderRadius: 8, border: "none",
                cursor: "pointer", fontSize: 14, fontWeight: active ? 600 : 400,
                background: active ? "#4f46e5" : "#f3f4f6",
                color: active ? "#fff" : "#374151",
                transition: "all 0.15s",
              }}
            >
              <Icon size={16} /> {t.label}
            </button>
          );
        })}

        {/* Days filter */}
        <div style={{ marginRight: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, color: "#6b7280" }}>الفترة:</span>
          {[7, 30, 90].map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              style={{
                padding: "6px 12px", borderRadius: 6, border: "1px solid #d1d5db",
                background: days === d ? "#ede9fe" : "#fff", cursor: "pointer",
                fontSize: 13, color: days === d ? "#4f46e5" : "#374151",
              }}
            >
              {d} يوم
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div style={{ padding: 12, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, marginBottom: 16, color: "#b91c1c" }}>
          ⚠️ {error}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: "#6b7280" }}>
          جاري التحميل...
        </div>
      )}

      {/* ── Tab: Problems ─────────────────────────────────────── */}
      {!loading && tab === "problems" && problems && (
        <div>
          {/* KPIs */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginBottom: 24 }}>
            <KpiCard
              label="إجمالي الرسائل"
              value={problems.total_messages?.toLocaleString()}
              color="#4f46e5"
              icon="💬"
            />
            <KpiCard
              label="بدون إجابة"
              value={problems.unanswered_count?.toLocaleString()}
              sub={`${problems.unanswered_rate}%`}
              color="#dc2626"
              icon="❓"
            />
            <KpiCard
              label="أكثر مشكلة"
              value={(problems.top_problems?.[0]?.problem || "—").slice(0, 25)}
              color="#059669"
              icon="🔥"
            />
          </div>

          {/* Top Problems Chart */}
          <Section title="أكثر المشاكل المطروحة">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={problems.top_problems?.slice(0, 10) || []} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" />
                <YAxis type="category" dataKey="problem" width={160} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#4f46e5" name="عدد الأسئلة" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Section>

          {/* Keywords */}
          <Section title="أكثر الكلمات المفتاحية">
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {(problems.top_keywords || []).slice(0, 30).map((kw: any, i: number) => (
                <span key={i} style={{
                  padding: "4px 10px", borderRadius: 20,
                  background: i < 5 ? "#ede9fe" : "#f3f4f6",
                  color: i < 5 ? "#4f46e5" : "#374151",
                  fontSize: 13, fontWeight: i < 5 ? 600 : 400,
                }}>
                  {kw.word} ({kw.count})
                </span>
              ))}
            </div>
          </Section>
        </div>
      )}

      {/* ── Tab: Neighborhoods ───────────────────────────────── */}
      {!loading && tab === "neighborhoods" && neighborhoods && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginBottom: 24 }}>
            <KpiCard label="محادثات محللة" value={neighborhoods.total_analyzed?.toLocaleString()} color="#4f46e5" icon="🔍" />
            <KpiCard label="أحياء مُعرَّفة" value={neighborhoods.neighborhoods_found} color="#0891b2" icon="🏘️" />
            <KpiCard
              label="أكثر حي شكاوى"
              value={(neighborhoods.top_neighborhoods?.[0]?.neighborhood || "—").slice(0, 20)}
              color="#dc2626"
              icon="📍"
            />
          </div>

          <Section title="أكثر الأحياء شكاوى">
            {neighborhoods.top_neighborhoods?.length ? (
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={neighborhoods.top_neighborhoods.slice(0, 12)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="neighborhood" width={140} tick={{ fontSize: 11 }} />
                  <Tooltip
                    formatter={(val: any, _: any, props: any) => [val, `أكثر مشكلة: ${props.payload?.top_problem || "—"}`]}
                  />
                  <Bar dataKey="complaints" fill="#dc2626" name="الشكاوى" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState msg="لم يُعرَّف أي حي من نصوص المحادثات — تأكد أن المواطنين يذكرون أسماء أحيائهم" />
            )}
          </Section>

          {neighborhoods.top_neighborhoods?.length > 0 && (
            <Section title="تفاصيل الأحياء">
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "#4f46e5", color: "#fff" }}>
                    <th style={th}>الحي / المنطقة</th>
                    <th style={th}>عدد الشكاوى</th>
                    <th style={th}>أكثر مشكلة</th>
                  </tr>
                </thead>
                <tbody>
                  {neighborhoods.top_neighborhoods.map((n: any, i: number) => (
                    <tr key={i} style={{ background: i % 2 ? "#f9fafb" : "#fff" }}>
                      <td style={td}>{n.neighborhood}</td>
                      <td style={{ ...td, textAlign: "center", fontWeight: 600, color: "#dc2626" }}>{n.complaints}</td>
                      <td style={td}>{n.top_problem}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
          )}
        </div>
      )}

      {/* ── Tab: RAG Metrics ─────────────────────────────────── */}
      {!loading && tab === "rag_metrics" && ragMetrics && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 12, marginBottom: 24 }}>
            {[
              { label: "Precision@5", val: ragMetrics.avg_precision, color: "#4f46e5", tip: "من المسترجع، كم ذو صلة؟" },
              { label: "Recall@5",    val: ragMetrics.avg_recall,    color: "#0891b2", tip: "كم استرجعنا من الصحيح؟" },
              { label: "F1 Score",    val: ragMetrics.avg_f1,        color: "#059669", tip: "التوازن بين Precision و Recall" },
              { label: "MRR",         val: ragMetrics.avg_mrr,       color: "#d97706", tip: "متوسط ترتيب أول نتيجة صحيحة" },
              { label: "Hit@5",       val: ragMetrics.hit_rate,      color: "#7c3aed", tip: "هل وُجد جواب في أفضل 5؟" },
            ].map((m, i) => (
              <div key={i} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10, padding: 16, textAlign: "center" }} title={m.tip}>
                <div style={{ fontSize: 24, fontWeight: 700, color: m.color }}>
                  {ragMetrics.total_evals > 0 ? (m.val * 100).toFixed(1) + "%" : "—"}
                </div>
                <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>{m.label}</div>
              </div>
            ))}
          </div>

          {ragMetrics.total_evals === 0 ? (
            <EmptyState msg="لم يتم تسجيل تقييمات بعد — ستبدأ تلقائياً مع أول محادثة" />
          ) : (
            <>
              {/* Radar */}
              <Section title="نظرة شاملة على جودة الـ RAG">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
                  <ResponsiveContainer width="100%" height={260}>
                    <RadarChart data={[
                      { metric: "Precision", value: ragMetrics.avg_precision * 100 },
                      { metric: "Recall",    value: ragMetrics.avg_recall * 100 },
                      { metric: "F1",        value: ragMetrics.avg_f1 * 100 },
                      { metric: "MRR",       value: ragMetrics.avg_mrr * 100 },
                      { metric: "Hit@5",     value: ragMetrics.hit_rate * 100 },
                    ]}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
                      <PolarRadiusAxis domain={[0, 100]} tick={false} />
                      <Radar dataKey="value" stroke="#4f46e5" fill="#4f46e5" fillOpacity={0.3} />
                    </RadarChart>
                  </ResponsiveContainer>

                  {/* Daily F1 trend */}
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={ragMetrics.daily || []}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                      <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                      <Tooltip formatter={(v: any) => `${(v * 100).toFixed(1)}%`} />
                      <Legend />
                      <Line type="monotone" dataKey="f1"        stroke="#4f46e5" name="F1"        strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="precision" stroke="#0891b2" name="Precision" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="recall"    stroke="#059669" name="Recall"    strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Section>
            </>
          )}

          <div style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 8, padding: 12, fontSize: 13, color: "#92400e", marginTop: 16 }}>
            💡 <strong>ملاحظة:</strong> هذه المقاييس محسوبة تلقائياً (proxy evaluation). للحصول على Precision/Recall دقيق، أضف Ground Truth labels عبر واجهة التقييم.
          </div>
        </div>
      )}

      {/* ── Tab: LLM Usage ───────────────────────────────────── */}
      {!loading && tab === "llm_usage" && isAdmin && llmUsage && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 24 }}>
            <KpiCard label="إجمالي الطلبات" value={llmUsage.total_calls} color="#4f46e5" icon="🤖" />
            <KpiCard label="معدل النجاح" value={`${llmUsage.success_rate}%`} color="#059669" icon="✅" />
            <KpiCard label="متوسط الزمن" value={`${llmUsage.avg_latency_ms}ms`} color="#d97706" icon="⏱️" />
            <KpiCard label="Tokens الإجمالي" value={(llmUsage.total_tokens_in + llmUsage.total_tokens_out).toLocaleString()} color="#7c3aed" icon="🔤" />
          </div>

          <Section title="الطلبات بالساعة">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={llmUsage.hourly || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="calls"  stroke="#4f46e5" name="طلبات" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="errors" stroke="#dc2626" name="أخطاء" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Section>

          {llmUsage.recent_errors?.length > 0 && (
            <Section title="آخر الأخطاء">
              {llmUsage.recent_errors.map((e: any, i: number) => (
                <div key={i} style={{ padding: "8px 12px", background: "#fef2f2", borderRadius: 6, marginBottom: 6, fontSize: 12, color: "#b91c1c" }}>
                  <strong>{e.ts?.slice(0, 19)}</strong> — {e.model} — {e.error}
                </div>
              ))}
            </Section>
          )}
        </div>
      )}

      {/* ── Tab: Admin Controls ──────────────────────────────── */}
      {!loading && tab === "admin" && isAdmin && (
        <div>
          {/* KB Health */}
          {kbHealth && (
            <Section title="صحة قاعدة المعرفة (Embeddings)">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
                <KpiCard label="إجمالي الـ Chunks" value={kbHealth.total_chunks} color="#4f46e5" icon="📄" />
                <KpiCard label="مع Embeddings" value={kbHealth.total_embeddings} color="#059669" icon="🧠" />
                <KpiCard label="بدون Embeddings" value={kbHealth.missing_embeddings} color={kbHealth.missing_embeddings > 0 ? "#dc2626" : "#059669"} icon="⚠️" />
                <KpiCard label="التغطية" value={`${kbHealth.coverage_pct}%`} color="#7c3aed" icon="📊" />
              </div>

              {kbHealth.missing_embeddings > 0 && (
                <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 13 }}>
                  ⚠️ يوجد <strong>{kbHealth.missing_embeddings}</strong> مستند بدون embeddings — إعادة البناء مطلوبة.
                </div>
              )}

              {/* Rebuild Controls */}
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 20 }}>
                <button
                  onClick={() => startRebuild(false)}
                  disabled={rebuildRunning}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "10px 20px", borderRadius: 8, border: "none",
                    background: rebuildRunning ? "#d1d5db" : "#4f46e5",
                    color: "#fff", cursor: rebuildRunning ? "not-allowed" : "pointer",
                    fontSize: 14, fontWeight: 600,
                  }}
                >
                  <RefreshCcw size={16} style={{ animation: rebuildRunning ? "spin 1s linear infinite" : "none" }} />
                  بناء المفقود فقط
                </button>
                <button
                  onClick={() => startRebuild(true)}
                  disabled={rebuildRunning}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "10px 20px", borderRadius: 8, border: "2px solid #dc2626",
                    background: "#fff", color: "#dc2626",
                    cursor: rebuildRunning ? "not-allowed" : "pointer",
                    fontSize: 14, fontWeight: 600, opacity: rebuildRunning ? 0.5 : 1,
                  }}
                >
                  <RefreshCcw size={16} /> إعادة بناء الكل
                </button>
                <button
                  onClick={load}
                  style={{
                    padding: "10px 16px", borderRadius: 8, border: "1px solid #d1d5db",
                    background: "#f9fafb", cursor: "pointer", fontSize: 14,
                  }}
                >
                  🔄 تحديث
                </button>
              </div>

              {/* Rebuild Progress */}
              {rebuildStatus && (
                <div style={{ background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 10, padding: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    {rebuildStatus.running
                      ? <Activity size={16} color="#4f46e5" />
                      : rebuildStatus.errors > 0
                      ? <AlertCircle size={16} color="#dc2626" />
                      : <CheckCircle size={16} color="#059669" />
                    }
                    <strong style={{ fontSize: 14 }}>
                      {rebuildStatus.running ? "جاري البناء..." : rebuildStatus.finished_at ? "اكتمل" : "لم يبدأ بعد"}
                    </strong>
                  </div>

                  {rebuildStatus.total > 0 && (
                    <>
                      <div style={{ background: "#e5e7eb", borderRadius: 4, height: 10, marginBottom: 8 }}>
                        <div style={{
                          height: 10, borderRadius: 4,
                          width: `${rebuildStatus.progress_pct}%`,
                          background: rebuildStatus.errors > 0 ? "#f59e0b" : "#4f46e5",
                          transition: "width 0.3s",
                        }} />
                      </div>
                      <div style={{ display: "flex", gap: 20, fontSize: 13, color: "#6b7280" }}>
                        <span>المجموع: <strong>{rebuildStatus.total}</strong></span>
                        <span>تم: <strong style={{ color: "#059669" }}>{rebuildStatus.done}</strong></span>
                        <span>أخطاء: <strong style={{ color: "#dc2626" }}>{rebuildStatus.errors}</strong></span>
                        <span>{rebuildStatus.progress_pct}%</span>
                      </div>
                    </>
                  )}

                  {rebuildStatus.last_error && (
                    <div style={{ fontSize: 12, color: "#b91c1c", marginTop: 8 }}>
                      آخر خطأ: {rebuildStatus.last_error}
                    </div>
                  )}
                </div>
              )}
            </Section>
          )}
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

// ── Helper components ─────────────────────────────────────────

function KpiCard({ label, value, sub, color, icon }: any) {
  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10,
      padding: 16, borderTop: `3px solid ${color}`,
    }}>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 6 }}>{icon} {label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value ?? "—"}</div>
      {sub && <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10, padding: 20, marginBottom: 20 }}>
      <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 600, color: "#1e1b4b" }}>{title}</h3>
      {children}
    </div>
  );
}

function EmptyState({ msg }: { msg: string }) {
  return (
    <div style={{ textAlign: "center", padding: "32px 16px", color: "#9ca3af" }}>
      <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
      <div style={{ fontSize: 13 }}>{msg}</div>
    </div>
  );
}

const th: React.CSSProperties = {
  padding: "8px 12px", textAlign: "right", fontWeight: 600, fontSize: 12,
};
const td: React.CSSProperties = {
  padding: "8px 12px", fontSize: 13, borderTop: "1px solid #f3f4f6",
};
