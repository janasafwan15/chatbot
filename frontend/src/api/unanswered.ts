// frontend/src/api/unanswered.ts
import { apiFetch } from "./http";

export interface QuestionOut {
  question_id:      number;
  question:         string;
  asked_by:         string;
  asked_at:         string;
  status:           "pending" | "answered";
  answer?:          string | null;
  answered_by?:     number | null;
  answered_by_name?: string | null;
  answered_at?:     string | null;
  conversation_id?: number | null;
}

export interface QuestionStats {
  pending_count:  number;
  answered_count: number;
  total_count:    number;
}

// ── Submit (مواطن) ───────────────────────────────────────────

export async function submitUnanswered(
  question: string,
  conversationId?: number
): Promise<{ ok: boolean; question_id?: number; duplicate?: boolean }> {
  return apiFetch("/unanswered", {
    method: "POST",
    body: { question, conversation_id: conversationId ?? null },
  });
}

// ── List (موظف/إدارة) ────────────────────────────────────────

export async function listUnanswered(
  status?: "pending" | "answered"
): Promise<QuestionOut[]> {
  const qs = status ? `?status=${status}` : "";
  return apiFetch<QuestionOut[]>(`/unanswered${qs}`);
}

// ── Answer ───────────────────────────────────────────────────

export async function answerQuestion(
  questionId: number,
  answer: string
): Promise<{ ok: boolean; kb_id: number }> {
  return apiFetch(`/unanswered/${questionId}/answer`, {
    method: "POST",
    body: { answer },
  });
}

// ── Delete ───────────────────────────────────────────────────

export async function deleteQuestion(questionId: number): Promise<{ ok: boolean }> {
  return apiFetch(`/unanswered/${questionId}`, { method: "DELETE" });
}

// ── Stats ────────────────────────────────────────────────────

export async function getUnansweredStats(): Promise<QuestionStats> {
  return apiFetch<QuestionStats>("/unanswered/stats/summary");
}
