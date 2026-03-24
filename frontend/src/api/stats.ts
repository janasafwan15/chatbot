import { apiFetch, getApiBase } from "./http";

export type Overview = {
  total_conversations: number;
  total_messages: number;
  avg_messages_per_conversation: number;
  answer_found_rate: number; // 0..1
  avg_intent_conf: number;   // 0..1
};

export type DailyResp = {
  conversations_daily: Array<{ day: string; conversations: number }>;
  messages_daily: Array<{ day: string; messages: number }>;
};

export type PeakHoursResp = {
  days: number;
  hours: Array<{ hour: string; total: number }>;
};

export type TopIntentsResp = {
  days: number;
  top_intents: Array<{ intent: string; total: number }>;
};

export type ComplaintsSummaryResp = {
  days: number;
  total_complaints: number;
  top_complaint: string;
  breakdown: Array<{ category: string; total: number; percent: number }>;
};

export type ResponseModesResp = {
  days: number;
  response_modes: Array<{ mode: string; total: number }>;
};

export type KbUsageResp = {
  days: number;
  kb_usage: Array<{ source_file: string; total: number }>;
};

export type QualityResp = {
  days: number;
  answer_found_rate: number;
  avg_best_score: number;
  best_score_buckets: Array<{ bucket: string; total: number }>;
};

export type ConvRatingsSummaryRangeResp = {
  from: string | null;
  to: string | null;
  total_ratings: number;
  avg_rating: number;
  satisfaction_rate: number;
  star_distribution: Array<{ stars: number; total: number }>;
};

export type ConvRatingsDailyRangeResp = {
  from: string | null;
  to: string | null;
  daily: Array<{ day: string; avg_rating: number; total: number }>;
};

export type RecentRatingsRangeResp = {
  from: string | null;
  to: string | null;
  items: Array<{ conversation_id: number; stars: number; comment: string; submitted_at: string }>;
};

export type LowRatedConversationsResp = {
  days: number;
  threshold: number;
  items: Array<{
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
  }>;
};

export type EmployeesActivityResp = {
  days: number;
  message_link_col?: string | null;
  conversation_link_col?: string | null;
  employees: {
    user_id: number;
    name: string;
    logins: number;
    last_activity: string | null;
    active_minutes: number;
    handled_messages?: number;
    handled_conversations?: number;
    status: string;
  }[];
};

async function apiFetchBlob(path: string, token: string): Promise<Blob> {
  const base = getApiBase();
  const res = await fetch(`${base}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return res.blob();
}

export const StatsAPI = {
  overview: (token: string) =>
    apiFetch<Overview>("/stats/overview", { token }),

  daily: (limit: number, token: string) =>
    apiFetch<DailyResp>(`/stats/daily?limit=${limit}`, { token }),

  peakHours: (days: number, token: string) =>
    apiFetch<PeakHoursResp>(`/stats/peak-hours?days=${days}`, { token }),

  topIntents: (days: number, limit: number, token: string) =>
    apiFetch<TopIntentsResp>(`/stats/top-intents?days=${days}&limit=${limit}`, { token }),

  complaintsSummary: (days: number, token: string) =>
    apiFetch<ComplaintsSummaryResp>(`/stats/complaints-summary?days=${days}`, { token }),

  lowRatedConversations: (days: number, threshold: number, limit: number, token: string) =>
    apiFetch<LowRatedConversationsResp>(
      `/stats/low-rated-conversations?days=${days}&threshold=${threshold}&limit=${limit}`,
      { token }
    ),

  employeesActivity: (days: number, token: string) =>
    apiFetch<EmployeesActivityResp>(`/stats/employees-activity?days=${days}`, { token }),

  responseModes: (days: number, token: string) =>
    apiFetch<ResponseModesResp>(`/stats/response-modes?days=${days}`, { token }),

  kbUsage: (limit: number, days: number, token: string) =>
    apiFetch<KbUsageResp>(`/stats/kb-usage?limit=${limit}&days=${days}`, { token }),

  quality: (days: number, token: string) =>
    apiFetch<QualityResp>(`/stats/quality?days=${days}`, { token }),

  conversationRatingsSummaryRange: (token: string, from_date?: string, to_date?: string) => {
    const params = new URLSearchParams();
    if (from_date) params.set("from_date", from_date);
    if (to_date) params.set("to_date", to_date);
    return apiFetch<ConvRatingsSummaryRangeResp>(`/stats/conversation-ratings-summary-range?${params}`, { token });
  },

  conversationRatingsDailyRange: (token: string, from_date?: string, to_date?: string) => {
    const params = new URLSearchParams();
    if (from_date) params.set("from_date", from_date);
    if (to_date) params.set("to_date", to_date);
    return apiFetch<ConvRatingsDailyRangeResp>(`/stats/conversation-ratings-daily-range?${params}`, { token });
  },

  recentRatingsRange: (token: string, limit = 50, from_date?: string, to_date?: string) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (from_date) params.set("from_date", from_date);
    if (to_date) params.set("to_date", to_date);
    return apiFetch<RecentRatingsRangeResp>(`/stats/recent-ratings-range?${params}`, { token });
  },

  exportMonthlyExcel: (days: number, token: string) =>
    apiFetchBlob(`/stats/export/monthly.xlsx?days=${days}`, token),

  exportMonthlyPDF: (days: number, token: string) =>
    apiFetchBlob(`/stats/export/monthly.pdf?days=${days}`, token),

  exportEmployeesExcel: (days: number, token: string) =>
    apiFetchBlob(`/stats/export/employees.xlsx?days=${days}`, token),

  exportEmployeesPDF: (days: number, token: string) =>
    apiFetchBlob(`/stats/export/employees.pdf?days=${days}`, token),
};
// ── Types for new features ──────────────────────────────────

export type ChatProblemsResp = {
  days: number;
  total_messages: number;
  unanswered_count: number;
  unanswered_rate: number;
  top_problems: Array<{ problem: string; count: number; resolved_pct: number }>;
  top_keywords: Array<{ word: string; count: number }>;
};

export type NeighborhoodComplaintsResp = {
  days: number;
  total_analyzed: number;
  neighborhoods_found: number;
  top_neighborhoods: Array<{ neighborhood: string; complaints: number; top_problem: string }>;
};

export type QuestionsTrendResp = {
  days: number;
  daily: Array<{ day: string; total_questions: number; answered: number; unanswered: number; avg_confidence: number }>;
};

export type RagEvalMetricsResp = {
  days: number;
  total_evals: number;
  avg_precision: number;
  avg_recall: number;
  avg_f1: number;
  avg_mrr: number;
  hit_rate: number;
  daily: Array<{ day: string; evals: number; precision: number; recall: number; f1: number; mrr: number; hit_rate: number }>;
};

export type LLMUsageResp = {
  hours: number;
  total_calls: number;
  success_rate: number;
  avg_latency_ms: number;
  total_tokens_in: number;
  total_tokens_out: number;
  recent_errors: Array<{ ts: string; model: string; error: string }>;
  calls_per_model: Record<string, { calls: number; tokens_in: number; tokens_out: number }>;
  hourly: Array<{ hour: string; calls: number; errors: number; avg_latency_ms: number }>;
};

export type EmbedRebuildStatus = {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  done: number;
  errors: number;
  last_error: string;
  progress_pct: number;
};

// ── Extend StatsAPI ─────────────────────────────────────────
export const AnalyticsAPI = {
  chatProblems: (days: number, token: string) =>
    apiFetch<ChatProblemsResp>(`/stats/chat-problems?days=${days}`, { token }),

  neighborhoodComplaints: (days: number, token: string) =>
    apiFetch<NeighborhoodComplaintsResp>(`/stats/neighborhood-complaints?days=${days}`, { token }),

  questionsTrend: (days: number, token: string) =>
    apiFetch<QuestionsTrendResp>(`/stats/questions-trend?days=${days}`, { token }),

  ragEvalMetrics: (days: number, token: string) =>
    apiFetch<RagEvalMetricsResp>(`/stats/rag-eval-metrics?days=${days}`, { token }),

  llmUsage: (hours: number, token: string) =>
    apiFetch<LLMUsageResp>(`/admin/llm-usage?hours=${hours}`, { token }),

  rebuildEmbeddings: (overwrite: boolean, token: string) =>
    apiFetch<{ ok: boolean; message: string }>(`/admin/rebuild-embeddings?overwrite=${overwrite}`, { token, method: "POST" }),

  rebuildEmbeddingsStatus: (token: string) =>
    apiFetch<EmbedRebuildStatus>(`/admin/rebuild-embeddings/status`, { token }),

  kbHealth: (token: string) =>
    apiFetch<{ total_chunks: number; total_embeddings: number; missing_embeddings: number; coverage_pct: number; chunks_without_embeddings: Array<{ chunk_id: string; source_file: string; preview: string }> }>(`/admin/kb-health`, { token }),
};
